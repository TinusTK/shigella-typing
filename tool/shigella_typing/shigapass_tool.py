"""
Tool 1 - ShigaPass typing of assemblies.

Runs ShigaPass (Yassine et al. 2023) on each assembly and writes
shigapass_report.tsv with one row per input, always, even when ShigaPass
finds nothing or fails on a sample.

How ShigaPass is called, and why:

- ShigaPass.sh runs with `set -e`, so one bad genome stops the whole batch,
  and it names samples by cutting the file name at the first dot. Each
  assembly is therefore copied to a safe name (s0001.fasta, ...) and run on
  its own; results are mapped back to the real sample names.
- `ShigaPass.sh -u` builds BLAST databases inside the database folder, which
  is read-only in Galaxy. The databases are copied to the work folder and
  indexed once with makeblastdb (exactly what -u does), then every sample
  runs without -u.
- ShigaPass never touches the network.
"""

import glob
import gzip
import os
import re
import shutil
import tempfile

from shigella_typing import __version__
from shigella_typing.utils import (check_unique, last_line, log, run,
                                   sample_name_from_path, write_tsv)

REPORT_COLUMNS = [
    "sample", "rfb", "rfb_hits", "rfb_pct", "mlst_st", "fliC", "crispr", "ipaH",
    "predicted_serotype", "predicted_flexserotype", "comments",
    "species_shigapass", "serotype_shigapass",
    "warnings", "shigapass_version", "tool_version",
]

# Columns shared with the combined report (sample ... serotype_shigapass).
SHIGAPASS_COLUMNS = REPORT_COLUMNS[:13]

SUMMARY_HEADER = ("Name;rfb;rfb_hits,(%);MLST;fliC;CRISPR;ipaH;"
                  "Predicted_Serotype;Predicted_FlexSerotype;Comments")

RAW_OUTPUTS = {
    "summary": "ShigaPass_summary.csv",
    "flex_summary": "ShigaPass_Flex_summary.csv",
}

BLAST_INDEX = ("*.ndb", "*.nhr", "*.nin", "*.nsq", "*.not", "*.ntf", "*.nto", "*.njs", "*.nal")

NOT_SHIGELLA = "Not Shigella/EIEC"


# --------------------------------------------------------------------------
# Species / serotype names
# --------------------------------------------------------------------------

def species_serotype(predicted, flex):
    """Human-readable (species, serotype) for a ShigaPass call.

    SS -> S. sonnei / -; SF1-5 + 1b -> S. flexneri / S. flexneri 1b;
    SB2 -> S. boydii / S. boydii 2; SD3/SD16 -> S. dysenteriae 3/16;
    EIEC, Shigella spp., Not Shigella/EIEC -> themselves / -.
    """
    p = predicted.strip()
    if p == "SS":
        return "S. sonnei", "-"
    if p == "SF1-5":
        if flex in ("", "-", "Unknown"):
            return "S. flexneri", "S. flexneri 1-5 (subserotype unknown)"
        return "S. flexneri", f"S. flexneri {flex}"
    if p == "SF6":
        return "S. flexneri", "S. flexneri 6"
    if p.startswith("SDprov"):
        return "S. dysenteriae", f"S. dysenteriae provisional {p[len('SDprov'):]}"
    m = re.fullmatch(r"S([BD])(\d+(?:/S[BD]\d+)*)", p)
    if m:
        species = "S. boydii" if m.group(1) == "B" else "S. dysenteriae"
        numbers = re.sub(r"S[BD]", "", m.group(2))
        return species, f"{species} {numbers}"
    if p in ("EIEC", "Shigella spp.", NOT_SHIGELLA):
        return p, "-"
    return p or "-", "-"


def is_known_call(predicted):
    p = predicted.strip()
    return (p in ("SS", "SF1-5", "SF6", "EIEC", "Shigella spp.", NOT_SHIGELLA)
            or p.startswith("SDprov")
            or re.fullmatch(r"S[BD]\d+(?:/S[BD]\d+)*", p) is not None)


# --------------------------------------------------------------------------
# Finding ShigaPass and its databases
# --------------------------------------------------------------------------

def find_shigapass():
    script = shutil.which("ShigaPass.sh")
    if not script:
        raise SystemExit("Error: ShigaPass.sh not found on PATH (install bioconda shigapass)")
    return script


def find_database(script, given=None):
    """--shigapass-db, else $SP_DB_PATH (set by the conda package), else the
    package's share/shigapass-*/db next to ShigaPass.sh (containers)."""
    candidates = [given, os.environ.get("SP_DB_PATH")]
    prefix = os.path.dirname(os.path.dirname(os.path.realpath(script)))
    candidates += sorted(glob.glob(os.path.join(prefix, "share", "shigapass-*", "db")), reverse=True)
    for c in candidates:
        if c and os.path.isfile(os.path.join(c, "ShigaPass_meta_profiles_v5.csv")):
            return c
    raise SystemExit("Error: ShigaPass databases not found; use --shigapass-db")


def shigapass_version(script):
    code, out, err = run(["bash", script, "-v"])
    m = re.search(r"version\s+(\S+)", out + err)
    return m.group(1) if m else "unknown"


def prepare_database(src, workdir):
    """Copy the databases to a writable folder and index them once."""
    db = os.path.join(workdir, "db")
    shutil.copytree(src, db, ignore=shutil.ignore_patterns(*BLAST_INDEX))
    for fasta in sorted(glob.glob(os.path.join(db, "*", "*.fasta"))):
        code, out, err = run(["makeblastdb", "-dbtype", "nucl", "-in", fasta])
        if code != 0:
            raise SystemExit(f"Error: makeblastdb failed on {os.path.basename(fasta)}: "
                             f"{last_line(err or out)}")
    return db


# --------------------------------------------------------------------------
# Input checks
# --------------------------------------------------------------------------

def open_text(path):
    with open(path, "rb") as fh:
        gz = fh.read(2) == b"\x1f\x8b"
    return gzip.open(path, "rt", errors="replace") if gz else open(path, errors="replace")


def copy_fasta(src, dest):
    """Copy (and gunzip) a FASTA file; return a problem description or None."""
    try:
        with open_text(src) as fin, open(dest, "w") as fout:
            n_seq, n_bases, first = 0, 0, None
            for line in fin:
                s = line.strip()
                if not s:
                    continue
                if first is None:
                    first = s
                    if not s.startswith(">"):
                        return "input is not FASTA"
                if s.startswith(">"):
                    n_seq += 1
                else:
                    n_bases += len(s)
                fout.write(line if line.endswith("\n") else line + "\n")
    except (OSError, EOFError) as exc:
        return f"cannot read input ({exc})"
    if first is None:
        return "input is empty"
    if n_bases == 0:
        return "input has no sequence"
    return None


# --------------------------------------------------------------------------
# Parsing ShigaPass output
# --------------------------------------------------------------------------

def parse_summary_line(line):
    """Split one ShigaPass_summary.csv row into report fields."""
    parts = line.rstrip("\n").split(";", 9)
    parts += [""] * (10 - len(parts))
    name, rfb, hits_pct, mlst, flic, crispr, ipah, pred, flex, comments = parts
    m = re.fullmatch(r"(.*),\((.*)\)", hits_pct.strip())
    hits, pct = (m.group(1), m.group(2)) if m else (hits_pct, "")
    if hits.strip() == "ND":
        pct = "ND"

    def dash(v):
        v = v.strip()
        return v if v else "-"

    return name, {
        "rfb": dash(rfb), "rfb_hits": dash(hits), "rfb_pct": dash(pct),
        "mlst_st": dash(mlst), "fliC": dash(flic), "crispr": dash(crispr),
        "ipaH": dash(ipah), "predicted_serotype": dash(pred),
        "predicted_flexserotype": dash(flex), "comments": comments.strip(),
    }


def warnings_for(fields):
    """Tool 1 warnings: facts from ShigaPass alone."""
    w = []
    pred = fields["predicted_serotype"]
    if fields["ipaH"] == "ipaH-":
        w.append("ipaH negative; not serotyped")
    elif fields["mlst_st"] == "none":
        w.append("no MLST profile")
    if pred == "SF6":
        w.append("S. flexneri 6 - no Flex-It genotype expected")
    if pred == "SF1-5" and fields["predicted_flexserotype"] in ("-", "Unknown"):
        w.append("S. flexneri subserotype unknown")
    if pred == "EIEC":
        w.append("ipaH positive but no Shigella profile matched; likely EIEC")
    if fields["comments"].startswith("More than one rfb"):
        w.append("multiple rfb detected")
    if not is_known_call(pred):
        w.append(f"unrecognised ShigaPass call '{pred}'")
    return w


def failed_row(sample, reason):
    row = {c: "-" for c in SHIGAPASS_COLUMNS}
    row.update(sample=sample, warnings=f"ShigaPass not run: {reason}")
    return row


# --------------------------------------------------------------------------
# Running
# --------------------------------------------------------------------------

def run_one(script, db, threads, fasta, workdir, tag):
    """Run ShigaPass on one safe-named FASTA; return (summary row, flex row, error)."""
    sdir = os.path.join(workdir, tag)
    os.makedirs(sdir)
    listfile = os.path.join(sdir, "list.txt")
    with open(listfile, "w") as fh:
        fh.write(fasta + "\n")
    outdir = os.path.join(sdir, "out")
    code, out, err = run(["bash", script, "-l", listfile, "-o", outdir,
                          "-p", db, "-t", str(threads)], cwd=sdir)
    summary_row = flex_row = None
    for fname, kind in ((RAW_OUTPUTS["summary"], "summary"), (RAW_OUTPUTS["flex_summary"], "flex")):
        path = os.path.join(outdir, fname)
        if not os.path.exists(path):
            continue
        with open(path) as fh:
            for line in fh:
                if line.split(";", 1)[0] == tag:
                    if kind == "summary":
                        summary_row = line.rstrip("\n")
                    else:
                        flex_row = line.rstrip("\n")
    error = None
    if summary_row is None:
        error = "ShigaPass failed"
        detail = [ln for ln in (err + out).splitlines()
                  if ln.strip() and "ABORTED" not in ln and "*" not in ln
                  and "An error occurred" not in ln]
        if detail:
            error += f" ({detail[-1].strip()})"
    return summary_row, flex_row, error


def type_assemblies(assemblies, names, threads=2, db=None, keep_work=None):
    """Type assemblies; return (rows, raw summary lines, raw flex lines)."""
    script = find_shigapass()
    db_src = find_database(script, db)
    version = shigapass_version(script)
    threads = max(1, min(12, int(threads)))  # ShigaPass accepts 1-12

    workdir = keep_work or tempfile.mkdtemp(prefix="shigapass_")
    os.makedirs(workdir, exist_ok=True)
    rows, raw_summary, raw_flex = [], [], []
    try:
        log(f"ShigaPass {version}; databases from {db_src}")
        dbdir = prepare_database(db_src, workdir)
        for i, (path, sample) in enumerate(zip(assemblies, names), 1):
            tag = f"s{i:04d}"
            fasta = os.path.join(workdir, f"{tag}.fasta")
            problem = copy_fasta(path, fasta)
            if problem:
                log(f"{sample}: {problem}")
                rows.append(failed_row(sample, problem))
                continue
            log(f"{sample}: running ShigaPass")
            summary, flex, error = run_one(script, dbdir, threads, fasta, workdir, tag)
            if error:
                log(f"{sample}: {error}")
                rows.append(failed_row(sample, error))
                continue
            _, fields = parse_summary_line(summary)
            species, serotype = species_serotype(fields["predicted_serotype"],
                                                 fields["predicted_flexserotype"])
            row = dict(sample=sample, **fields,
                       species_shigapass=species, serotype_shigapass=serotype,
                       warnings="; ".join(warnings_for(fields)))
            rows.append(row)
            raw_summary.append(sample + summary[len(tag):])
            if flex:
                raw_flex.append(sample + flex[len(tag):])
    finally:
        if not keep_work:
            shutil.rmtree(workdir, ignore_errors=True)
    for row in rows:
        row["shigapass_version"] = version
        row["tool_version"] = __version__
    return rows, raw_summary, raw_flex


# --------------------------------------------------------------------------
# Command line (shigella-typing shigapass)
# --------------------------------------------------------------------------

def write_raw(outdir, raw_outputs, raw_summary, raw_flex):
    if "summary" in raw_outputs:
        with open(os.path.join(outdir, RAW_OUTPUTS["summary"]), "w") as fh:
            fh.write("\n".join([SUMMARY_HEADER] + raw_summary) + "\n")
    if "flex_summary" in raw_outputs:
        with open(os.path.join(outdir, RAW_OUTPUTS["flex_summary"]), "w") as fh:
            fh.write("".join(line + "\n" for line in raw_flex))


def add_arguments(p):
    p.add_argument("--assembly", nargs="+", required=True, metavar="FASTA",
                   help="assembly FASTA file(s) (plain or gzipped)")
    p.add_argument("--name", nargs="+", metavar="NAME",
                   help="sample name for each assembly, in order "
                        "(default: file name without extension)")
    p.add_argument("--outdir", required=True, help="output folder")
    p.add_argument("--threads", type=int, default=2, help="threads (BLAST: 1-12, default 2)")
    p.add_argument("--raw-outputs", nargs="*", default=[],
                   choices=sorted(RAW_OUTPUTS) + ["json", "predictresults"],
                   help="also write the tools' own output files "
                        "(json/predictresults only with --with-mykrobe)")
    p.add_argument("--shigapass-db", help="ShigaPass_DataBases folder "
                                          "(default: the one installed with ShigaPass)")
    p.add_argument("--keep-work", metavar="DIR", help="keep ShigaPass's work files in DIR")
    g = p.add_argument_group("also run Mykrobe genotyping (needs reads)")
    g.add_argument("--with-mykrobe", action="store_true",
                   help="also genotype the reads with Mykrobe and write the combined report")
    g.add_argument("--reads-samplesheet", metavar="TSV",
                   help="reads per sample: TSV with header sample, r1, r2 (r2 empty for "
                        "single-end/ONT); matched to assemblies by sample name")
    g.add_argument("--ont", action="store_true", help="reads are Oxford Nanopore")
    g.add_argument("--memory", default="2048MB", help="Mykrobe memory (default 2048MB)")
    g.add_argument("--panels-dir", help="Mykrobe panels folder (default: bundled panels/)")


def main(args):
    names = args.name or [sample_name_from_path(a) for a in args.assembly]
    if len(names) != len(args.assembly):
        raise SystemExit("Error: give one --name per --assembly")
    check_unique(names)
    os.makedirs(args.outdir, exist_ok=True)

    if args.with_mykrobe:
        from shigella_typing import pipeline
        if not args.reads_samplesheet:
            raise SystemExit("Error: --with-mykrobe needs --reads-samplesheet")
        reads = {s: r for s, _, r in pipeline.read_samplesheet(args.reads_samplesheet)}
        samples = [(n, a, reads.get(n, [])) for n, a in zip(names, args.assembly)]
        samples += [(s, None, r) for s, r in reads.items() if s not in names]
        pipeline.type_samples(samples, args.outdir, args.threads, args.ont, args.memory,
                              args.panels_dir, args.shigapass_db, args.raw_outputs)
        return 0

    rows, raw_summary, raw_flex = type_assemblies(
        args.assembly, names, args.threads, args.shigapass_db, args.keep_work)
    report = os.path.join(args.outdir, "shigapass_report.tsv")
    write_tsv(report, REPORT_COLUMNS, rows)
    log(f"wrote {report} ({len(rows)} samples)")
    write_raw(args.outdir, args.raw_outputs, raw_summary, raw_flex)
    return 0
