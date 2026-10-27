"""
All three steps for matched assemblies and reads: ShigaPass on the
assemblies, Mykrobe on the reads (routed by the ShigaPass call), and the
combined report.

Used by tool 1's toggle (`shigapass --with-mykrobe`) and by `run`.
Assemblies and reads are paired by sample name; a sample with only one of
them still gets a row ("missing reads" / "missing assembly").
"""

import csv
import os

from shigella_typing import combine, mykrobe_tool, shigapass_tool
from shigella_typing.utils import log, write_tsv

# ShigaPass call -> Mykrobe scheme to try first (others: both, as auto)
ROUTE = {"SS": "sonnei", "SF1-5": "flexneri"}


def read_samplesheet(path, need_assembly=False):
    """Samplesheet TSV with a header: sample, r1, r2 (optional; empty for
    single-end/ONT) and, for `run`, assembly. Relative paths are taken
    relative to the samplesheet. Returns [(sample, assembly or None, [reads])]."""
    base = os.path.dirname(os.path.abspath(path))

    def resolve(p):
        p = (p or "").strip()
        return os.path.join(base, p) if p and not os.path.isabs(p) else p

    with open(path, newline="") as fh:
        reader = csv.DictReader(fh, delimiter="\t")
        cols = reader.fieldnames or []
        needed = ["sample", "r1"] + (["assembly"] if need_assembly else [])
        missing = [c for c in needed if c not in cols]
        if missing:
            raise SystemExit(f"Error: samplesheet {os.path.basename(path)} is missing "
                             f"column(s): {', '.join(missing)}")
        out, seen = [], set()
        for row in reader:
            sample = (row.get("sample") or "").strip()
            if not sample:
                continue
            if sample in seen:
                raise SystemExit(f"Error: duplicate sample in samplesheet: {sample}")
            seen.add(sample)
            reads = [resolve(row.get(c)) for c in ("r1", "r2") if (row.get(c) or "").strip()]
            out.append((sample, resolve(row.get("assembly")) or None, reads))
    return out


def type_samples(samples, outdir, threads=2, ont=False, memory="2048MB", panels=None,
                 shigapass_db=None, raw_outputs=()):
    """samples: [(sample, assembly or None, [reads])]. Writes shigapass_report.tsv,
    mykrobe_report.tsv and shigella_typing_report.tsv; returns combined rows."""
    os.makedirs(outdir, exist_ok=True)
    with_assembly = [(s, a) for s, a, _ in samples if a]
    sp_rows, raw_summary, raw_flex = [], [], []
    if with_assembly:
        sp_rows, raw_summary, raw_flex = shigapass_tool.type_assemblies(
            [a for _, a in with_assembly], [s for s, _ in with_assembly], threads, shigapass_db)
    sp_by = {r["sample"]: r for r in sp_rows}

    final_sp, my_rows = [], []
    for sample, assembly, reads in samples:
        sp = sp_by.get(sample)
        if sp is None:
            sp = shigapass_tool.failed_row(sample, "missing assembly")
            sp.update(shigapass_version=sp_rows[0]["shigapass_version"] if sp_rows else "-",
                      tool_version=shigapass_tool.__version__)
        final_sp.append(sp)
        if reads:
            prefer = ROUTE.get(sp["predicted_serotype"])
            my_rows.append(mykrobe_tool.genotype_reads(
                sample, reads, "auto", ont, threads, memory, panels, prefer=prefer,
                raw_dir=outdir, raw_outputs=[o for o in raw_outputs if o in mykrobe_tool.RAW_OUTPUTS]))
        else:
            row = {c: "-" for c in mykrobe_tool.REPORT_COLUMNS}
            row.update(sample=sample, mykrobe_scheme="not run",
                       warnings="Mykrobe not run: missing reads",
                       tool_version=mykrobe_tool.__version__)
            my_rows.append(row)

    write_tsv(os.path.join(outdir, "shigapass_report.tsv"), shigapass_tool.REPORT_COLUMNS, final_sp)
    write_tsv(os.path.join(outdir, "mykrobe_report.tsv"), mykrobe_tool.REPORT_COLUMNS, my_rows)
    shigapass_tool.write_raw(outdir, raw_outputs, raw_summary, raw_flex)
    out = os.path.join(outdir, "shigella_typing_report.tsv")
    rows = combine.write_combined(out, final_sp, my_rows)
    log(f"wrote {out} ({len(rows)} samples)")
    return rows


# --------------------------------------------------------------------------
# Command line (shigella-typing run)
# --------------------------------------------------------------------------

ALL_RAW = sorted(shigapass_tool.RAW_OUTPUTS) + list(mykrobe_tool.RAW_OUTPUTS)


def add_arguments(p):
    p.add_argument("--samplesheet", required=True,
                   help="TSV with header: sample, assembly, r1, r2 (r2 empty for single-end/ONT)")
    p.add_argument("--outdir", required=True, help="output folder")
    p.add_argument("--ont", action="store_true", help="reads are Oxford Nanopore")
    p.add_argument("--threads", type=int, default=2, help="threads (default 2)")
    p.add_argument("--memory", default="2048MB", help="Mykrobe memory (default 2048MB)")
    p.add_argument("--raw-outputs", nargs="*", default=[], choices=ALL_RAW,
                   help="also write the tools' own output files")
    p.add_argument("--panels-dir", help="Mykrobe panels folder (default: bundled panels/)")
    p.add_argument("--shigapass-db", help="ShigaPass_DataBases folder")


def main(args):
    samples = read_samplesheet(args.samplesheet, need_assembly=True)
    type_samples(samples, args.outdir, args.threads, args.ont, args.memory,
                 args.panels_dir, args.shigapass_db, args.raw_outputs)
    return 0
