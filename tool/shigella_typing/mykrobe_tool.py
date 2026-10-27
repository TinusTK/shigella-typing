"""
Tool 2 - Mykrobe Shigella genotyping of reads.

Runs Mykrobe (Hunt et al. 2019) with the bundled S. sonnei (Sonneityping) and
S. flexneri (Flex-It) panels, parses each result with the vendored
mykrobeshig, and writes mykrobe_report.tsv with one row per sample, always.

Scheme `auto` (default) runs both schemes and keeps the one whose species
coverage reaches mykrobeshig's threshold (sonnei 90, flexneri 85.5). A scheme
that fails its threshold still writes a genotype into the JSON; that genotype
and its QRDR calls are ignored.

QRDR mutations are read from the Mykrobe JSON here, from every drug entry:
the flexneri panel files them under 'ciprofloxacin', the sonnei panel under
'quinolones' (mykrobeshig reads only the former; see mykrobeshig/UPSTREAM.md).

Mykrobe always gets --panels_dir (bundled panels) and a private
--skeleton_dir, so it never downloads anything or writes outside the work
folder.
"""

import csv
import json
import os
import re
import shutil
import sys
import tempfile

from shigella_typing import __version__
from shigella_typing.utils import check_unique, last_line, log, run, write_tsv

REPORT_COLUMNS = [
    "sample", "mykrobe_scheme", "mykrobe_species_call", "genotype", "genotype_name",
    "genotype_confidence", "qrdr_mutations", "num_qrdr", "cipro_prediction",
    "species_coverage", "lowest_support_genotype_marker", "poorly_supported_markers",
    "additional_markers", "warnings", "mykrobe_version", "mykrobe_panel_version",
    "tool_version",
]

# Columns shared with the combined report (mykrobe_scheme ... additional_markers).
MYKROBE_COLUMNS = REPORT_COLUMNS[1:13]

SCHEMES = {
    # scheme: (mykrobeshig species name, species coverage threshold)
    "sonnei": ("S. sonnei", 90.0),
    "flexneri": ("S. flexneri", 85.5),
}
BORDERLINE = 1.0  # warn when species coverage is within this of the threshold

RAW_OUTPUTS = ("json", "predictresults")

HERE = os.path.dirname(os.path.abspath(__file__))


# --------------------------------------------------------------------------
# Panels and versions
# --------------------------------------------------------------------------

def find_panels(given=None):
    """--panels-dir, else $SHIGELLA_TYPING_PANELS, else the bundled panels/
    (next to the package in the Galaxy bundle, or at the repository root)."""
    for c in (given, os.environ.get("SHIGELLA_TYPING_PANELS"),
              os.path.join(HERE, "..", "panels"), os.path.join(HERE, "..", "..", "panels")):
        if c and os.path.isfile(os.path.join(c, "manifest.json")):
            return os.path.realpath(c)
    raise SystemExit("Error: Mykrobe panels not found; use --panels-dir")


def mykrobe_version():
    code, out, err = run(["mykrobe", "--version"])
    m = re.search(r"v?(\d+\.\d+\.\d+)", out + err)
    return m.group(1) if m else "unknown"


def panel_version(sample_json):
    """'20250902' from version.panel '20250902/20250902'."""
    return str(sample_json.get("version", {}).get("panel", "")).split("/")[0] or "-"


# --------------------------------------------------------------------------
# Reading results
# --------------------------------------------------------------------------

def load_json(path):
    with open(path) as fh:
        data = json.load(fh)
    return next(iter(data.values()))


def qrdr_calls(sample_json):
    """Called QRDR mutations from every drug entry predicted R, e.g.
    ['gyrA_D87G', 'gyrA_S83L', 'parC_S80I']."""
    found = set()
    for drug in sample_json.get("susceptibility", {}).values():
        if drug.get("predict") == "R":
            found.update(name.split("-")[0] for name in drug.get("called_by", {}))
    return sorted(found)


def cipro_prediction(n):
    if n == 0:
        return "no QRDR mutations"
    if n < 3:
        return "QRDR mutation(s): reduced susceptibility likely"
    return "QRDR triple mutant: resistance likely"


def run_mykrobeshig(jsons, prefix):
    """Run the vendored mykrobeshig unchanged; return (rows by (genome, scheme), tsv path)."""
    env = dict(os.environ, PYTHONPATH=HERE + os.pathsep + os.environ.get("PYTHONPATH", ""))
    code, out, err = run([sys.executable, "-m", "mykrobeshig.parser",
                          "--jsons", *jsons, "--prefix", prefix], env=env)
    tsv = prefix + "_predictResults.tsv"
    if code != 0 or not os.path.exists(tsv):
        return {}, None, last_line(err or out) or "mykrobeshig failed"
    with open(tsv) as fh:
        rows = {(r["genome"], r["scheme"]): r for r in csv.DictReader(fh, delimiter="\t")}
    return rows, tsv, None


def to_float(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def strip_lineage(genotype):
    return genotype[len("lineage"):] if genotype.startswith("lineage") else genotype


# --------------------------------------------------------------------------
# Deciding the call
# --------------------------------------------------------------------------

def borderline_warnings(results):
    w = []
    for scheme, res in results.items():
        cov = to_float(res["msh"].get("species_coverage")) if res.get("msh") else None
        threshold = SCHEMES[scheme][1]
        if cov is None or abs(cov - threshold) >= BORDERLINE:
            continue
        side = "just above" if cov >= threshold else "just below"
        w.append(f"species coverage {cov:g} {side} the {scheme} threshold ({threshold:g}) - check")
    return w


def decide(sample, results):
    """Build the report row from per-scheme results.

    results: {scheme: {"msh": mykrobeshig row or None, "json": dict or None,
                       "error": str or None}}
    """
    row = {c: "-" for c in REPORT_COLUMNS}
    row["sample"] = sample
    warnings = [f"Mykrobe failed ({s}): {r['error']}" for s, r in results.items() if r.get("error")]
    ok = {s: r for s, r in results.items() if r.get("msh") and r.get("json")}
    passed = [s for s, r in ok.items() if r["msh"]["species"] == SCHEMES[s][0]]
    versions = {s: panel_version(r["json"]) for s, r in ok.items()}

    if len(passed) == 1:
        scheme = passed[0]
        msh, js = ok[scheme]["msh"], ok[scheme]["json"]
        qrdr = qrdr_calls(js)
        genotype = strip_lineage(msh["final genotype"])
        row.update(
            mykrobe_scheme=scheme,
            mykrobe_species_call=msh["species"],
            genotype=genotype if genotype not in ("", "NA") else "uncalled",
            genotype_name=msh["name"] if msh["name"] not in ("", "NA") else "-",
            genotype_confidence=msh["confidence"] if msh["confidence"] not in ("", "NA") else "-",
            qrdr_mutations=";".join(qrdr) or "none",
            num_qrdr=str(len(qrdr)),
            cipro_prediction=cipro_prediction(len(qrdr)),
            species_coverage=msh["species_coverage"],
            lowest_support_genotype_marker=msh["lowest support for genotype marker"] or "-",
            poorly_supported_markers=msh["poorly supported markers"] or "-",
            additional_markers=msh["additional markers"] or "-",
            mykrobe_panel_version=versions[scheme],
        )
        if row["genotype"] == "uncalled":
            warnings.append("species matched but no genotype called")
        if row["genotype_confidence"] in ("weak", "moderate"):
            warnings.append(f"{row['genotype_confidence']} genotype confidence")
        if msh["additional markers"]:
            warnings.append("additional markers present - possible mixed sample/recombination")
    elif len(passed) == 2:
        row.update(mykrobe_scheme="both matched", mykrobe_species_call="S. sonnei and S. flexneri",
                   species_coverage="; ".join(f"{s} {ok[s]['msh']['species_coverage']}" for s in passed),
                   mykrobe_panel_version="; ".join(f"{s} {v}" for s, v in versions.items()))
        warnings.append("matched both schemes - check for mixed/contaminated sample")
    elif ok:
        calls = {r["msh"]["species"] for r in ok.values()}
        species = ("Not E. coli/Shigella" if calls == {"Not E. coli/Shigella"}
                   else "Unknown E. coli/Shigella")
        covs = [f"{s} {r['msh']['species_coverage']}" for s, r in ok.items()
                if r["msh"]["species_coverage"] not in ("", "NA")]
        row.update(mykrobe_scheme="none matched", mykrobe_species_call=species,
                   species_coverage="; ".join(covs) or "-",
                   mykrobe_panel_version="; ".join(f"{s} {v}" for s, v in versions.items()))
        warnings.append("Not S. sonnei/S. flexneri")
    else:
        row.update(mykrobe_scheme="not run")
    warnings += borderline_warnings(ok)
    row["warnings"] = "; ".join(warnings)
    return row


# --------------------------------------------------------------------------
# Running
# --------------------------------------------------------------------------

def check_reads(reads):
    for r in reads:
        if not os.path.isfile(r):
            return f"reads file not found: {os.path.basename(r)}"
        if os.path.getsize(r) == 0:
            return f"reads file is empty: {os.path.basename(r)}"
    return None


def run_mykrobe(sample, scheme, reads, ont, threads, memory, panels, workdir):
    """Run mykrobe predict for one scheme; return (json path, error)."""
    out = os.path.join(workdir, f"mykrobe.{scheme}.json")
    cmd = ["mykrobe", "predict", "--sample", sample, "--species", scheme,
           "--panels_dir", panels, "--skeleton_dir", os.path.join(workdir, "skeletons"),
           "--tmp", os.path.join(workdir, f"tmp_{scheme}") + os.sep,
           "--format", "json", "--out", out, "-t", str(threads), "-m", memory]
    if ont:
        cmd.append("--ont")
    cmd += ["--seq", *reads]
    env = dict(os.environ, PYTHONWARNINGS="ignore")
    code, so, se = run(cmd, cwd=workdir, env=env)
    if code != 0 or not os.path.isfile(out):
        msg = [ln for ln in (se + so).splitlines() if ln.strip() and "pkg_resources" not in ln]
        return None, (msg[-1].strip() if msg else f"exit code {code}")
    return out, None


def genotype_reads(sample, reads, scheme="auto", ont=False, threads=2, memory="2048MB",
                   panels=None, keep_work=None, raw_dir=None, raw_outputs=()):
    """Genotype one sample; return the report row.

    Raw outputs asked for in raw_outputs are written to raw_dir:
    <sample>.<scheme>.json and mykrobeshig_predictResults.tsv.
    """
    panels = find_panels(panels)
    reads = [os.path.abspath(r) for r in reads]  # Mykrobe runs inside the work folder
    version = mykrobe_version()
    schemes = list(SCHEMES) if scheme == "auto" else [scheme]
    workdir = keep_work or tempfile.mkdtemp(prefix="mykrobe_")
    os.makedirs(workdir, exist_ok=True)
    try:
        problem = check_reads(reads)
        if problem:
            log(f"{sample}: {problem}")
            row = {c: "-" for c in REPORT_COLUMNS}
            row.update(sample=sample, mykrobe_scheme="not run", warnings=f"Mykrobe not run: {problem}")
        else:
            # Mykrobe's mccortex fails on names with spaces etc.: give it a
            # safe name; the report keeps the real one.
            safe = re.sub(r"[^A-Za-z0-9._-]", "_", sample)
            results, jsons = {}, []
            for s in schemes:
                log(f"{sample}: mykrobe predict --species {s}")
                path, error = run_mykrobe(safe, s, reads, ont, threads, memory, panels, workdir)
                results[s] = {"error": error, "json_path": path}
                if path:
                    jsons.append(path)
            if jsons:
                rows, tsv, error = run_mykrobeshig(jsons, os.path.join(workdir, "mykrobeshig"))
                for s, r in results.items():
                    if not r["json_path"]:
                        continue
                    if error:
                        r["error"] = f"mykrobeshig: {error}"
                        continue
                    r["json"] = load_json(r["json_path"])
                    r["msh"] = rows.get((safe, s))
                    if r["msh"] is None:
                        r["error"] = "mykrobeshig gave no result"
                if raw_dir and "json" in raw_outputs:
                    for s, r in results.items():
                        if r["json_path"]:
                            shutil.copy(r["json_path"], os.path.join(raw_dir, f"{sample}.{s}.json"))
                if raw_dir and "predictresults" in raw_outputs and tsv:
                    shutil.copy(tsv, os.path.join(raw_dir, "mykrobeshig_predictResults.tsv"))
            row = decide(sample, results)
        row["mykrobe_version"] = version
        row["tool_version"] = __version__
        return row
    finally:
        if not keep_work:
            shutil.rmtree(workdir, ignore_errors=True)


# --------------------------------------------------------------------------
# Command line (shigella-typing mykrobe)
# --------------------------------------------------------------------------

def sample_name_from_reads(path):
    name = os.path.basename(path)
    name = re.sub(r"\.(fastq|fq)(\.gz|\.bz2)?$", "", name)
    return re.sub(r"(_R?1(_001)?|\.1)$", "", name)


def add_arguments(p):
    p.add_argument("--reads", nargs="+", required=True, metavar="FASTQ",
                   help="reads for ONE sample: R1 R2 (paired), one file (single-end), "
                        "or ONT file(s) with --ont")
    p.add_argument("--sample", help="sample name (default: from the first reads file)")
    p.add_argument("--outdir", required=True, help="output folder")
    p.add_argument("--scheme", choices=["auto", "sonnei", "flexneri"], default="auto",
                   help="genotyping scheme (default auto: run both, keep the one that matches)")
    p.add_argument("--ont", action="store_true", help="reads are Oxford Nanopore")
    p.add_argument("--threads", type=int, default=2, help="threads (default 2)")
    p.add_argument("--memory", default="2048MB", help="Mykrobe memory (default 2048MB)")
    p.add_argument("--raw-outputs", nargs="*", default=[], choices=RAW_OUTPUTS,
                   help="also write the Mykrobe JSON(s) and mykrobeshig's predictResults.tsv")
    p.add_argument("--panels-dir", help="Mykrobe panels folder (default: bundled panels/)")
    p.add_argument("--keep-work", metavar="DIR", help="keep Mykrobe's work files in DIR")


def main(args):
    sample = args.sample or sample_name_from_reads(args.reads[0])
    check_unique([sample])
    if not args.ont and len(args.reads) > 2:
        raise SystemExit("Error: give at most two reads files (R1 R2) unless --ont")
    os.makedirs(args.outdir, exist_ok=True)

    row = genotype_reads(sample, args.reads, args.scheme, args.ont, args.threads,
                         args.memory, args.panels_dir, args.keep_work,
                         raw_dir=args.outdir, raw_outputs=args.raw_outputs)

    report = os.path.join(args.outdir, "mykrobe_report.tsv")
    write_tsv(report, REPORT_COLUMNS, [row])
    log(f"{sample}: {row['mykrobe_scheme']} {row['genotype']} -> {report}")
    return 0
