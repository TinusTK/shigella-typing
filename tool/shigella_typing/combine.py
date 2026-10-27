"""
Tool 3 - Combine Shigella report.

Joins the ShigaPass report (tool 1) and the Mykrobe report (tool 2) on
`sample` and adds cross-check warnings. Tool 1's toggle uses the same code,
so both routes give the same combined report. Pure Python, no dependencies.

Output columns: the 13 ShigaPass columns, the 12 Mykrobe columns, one
`warnings` column (tool 1 + tool 2 + cross-check warnings), then versions.
"""

import csv
import os
import re

from shigella_typing import __version__
from shigella_typing.mykrobe_tool import MYKROBE_COLUMNS
from shigella_typing.shigapass_tool import NOT_SHIGELLA, SHIGAPASS_COLUMNS
from shigella_typing.utils import log, write_tsv

VERSION_COLUMNS = ["shigapass_version", "mykrobe_version", "mykrobe_panel_version", "tool_version"]
REPORT_COLUMNS = SHIGAPASS_COLUMNS + MYKROBE_COLUMNS + ["warnings"] + VERSION_COLUMNS

# Suffixes removed by --strip-suffixes (D10), longest first.
SUFFIXES = ["_assembly", "_contigs", ".contigs", ".fasta", ".fastq", ".fna", ".fa", ".fq"]

SCHEME_FOR_CALL = {"SS": "sonnei", "SF1-5": "flexneri"}
SPECIES_FOR_SCHEME = {"sonnei": "S. sonnei", "flexneri": "S. flexneri"}


# --------------------------------------------------------------------------
# Reading reports
# --------------------------------------------------------------------------

def read_reports(paths, required, what):
    """Rows from one or more reports of the same kind (e.g. one per sample)."""
    rows = []
    for path in paths:
        with open(path, newline="") as fh:
            reader = csv.DictReader(fh, delimiter="\t")
            missing = [c for c in required if c not in (reader.fieldnames or [])]
            if missing:
                raise SystemExit(f"Error: {os.path.basename(path)} is not a {what} report "
                                 f"(missing columns: {', '.join(missing)})")
            rows.extend(reader)
    return rows


def strip_suffixes(name):
    changed = True
    while changed:
        changed = False
        for s in SUFFIXES:
            if name.endswith(s) and len(name) > len(s):
                name, changed = name[: -len(s)], True
    return name


def index_by_sample(rows, what, strip=False):
    """{sample: row}; fail with a clear error on duplicate names."""
    out, dups = {}, []
    for row in rows:
        name = strip_suffixes(row["sample"]) if strip else row["sample"]
        if name in out and name not in dups:
            dups.append(name)
        out[name] = row
    if dups:
        raise SystemExit(f"Error: duplicate sample names in the {what} report(s): {', '.join(dups)}")
    return out


# --------------------------------------------------------------------------
# Cross-check warnings
# --------------------------------------------------------------------------

def cross_check(sp, my):
    """Cross-check warnings for one sample (sp / my may be None if missing)."""
    if sp is None:
        return ["Missing from ShigaPass report"]
    if my is None:
        return ["Missing from Mykrobe report"]
    call = sp["predicted_serotype"]
    species = sp["species_shigapass"]
    scheme = my["mykrobe_scheme"]
    if call == "-" or scheme in ("not run", "-"):
        return []  # one side was not run; its own warning says why

    if scheme in SPECIES_FOR_SCHEME:
        mykrobe_species = SPECIES_FOR_SCHEME[scheme]
        if call == NOT_SHIGELLA:
            return [f"Discordant: ShigaPass {NOT_SHIGELLA}, Mykrobe {mykrobe_species} - check assembly"]
        if SCHEME_FOR_CALL.get(call) != scheme:
            return [f"Discordant: ShigaPass {species_label(sp)}, Mykrobe {mykrobe_species} - check"]
        return []

    if scheme == "none matched":
        if call in SCHEME_FOR_CALL:
            return [f"ShigaPass {species_label(sp)} but Mykrobe did not match the "
                    f"{SCHEME_FOR_CALL[call]} scheme - check reads/assembly"]
        if call == NOT_SHIGELLA:
            if my["mykrobe_species_call"] == "Not E. coli/Shigella":
                return ["Not Shigella - check organism"]
            return []
        return [f"No Mykrobe genotyping scheme for {species}; serotype only"]
    return []


def species_label(sp):
    """'S. sonnei', 'S. flexneri 1b', 'S. flexneri 6', 'S. boydii 2', ..."""
    serotype = sp["serotype_shigapass"]
    return serotype if serotype not in ("", "-") else sp["species_shigapass"]


# --------------------------------------------------------------------------
# Combining
# --------------------------------------------------------------------------

def combine_rows(sp_rows, my_rows, strip=False):
    """Combined report rows: ShigaPass order first, then Mykrobe-only samples."""
    sp_by = index_by_sample(sp_rows, "ShigaPass", strip)
    my_by = index_by_sample(my_rows, "Mykrobe", strip)
    samples = list(sp_by) + [s for s in my_by if s not in sp_by]
    rows = []
    for sample in samples:
        sp, my = sp_by.get(sample), my_by.get(sample)
        row = {c: "-" for c in REPORT_COLUMNS}
        if sp:
            row.update({c: sp[c] for c in SHIGAPASS_COLUMNS})
            row["shigapass_version"] = sp.get("shigapass_version", "-")
        if my:
            row.update({c: my[c] for c in MYKROBE_COLUMNS})
            row["mykrobe_version"] = my.get("mykrobe_version", "-")
            row["mykrobe_panel_version"] = my.get("mykrobe_panel_version", "-")
        row["sample"] = sample
        warnings = []
        for part in (sp, my):
            if part and part.get("warnings"):
                warnings += [w.strip() for w in part["warnings"].split(";") if w.strip()]
        checks = cross_check(sp, my)
        if sp and my and checks and my["mykrobe_scheme"] == "none matched":
            # the cross-check says why nothing matched; drop the generic one
            warnings = [w for w in warnings if w != "Not S. sonnei/S. flexneri"]
        warnings += checks
        row["warnings"] = "; ".join(dict.fromkeys(warnings))
        row["tool_version"] = __version__
        rows.append(row)
    return rows


def write_combined(path, sp_rows, my_rows, strip=False):
    rows = combine_rows(sp_rows, my_rows, strip)
    write_tsv(path, REPORT_COLUMNS, rows)
    return rows


# --------------------------------------------------------------------------
# Command line (shigella-typing combine)
# --------------------------------------------------------------------------

def add_arguments(p):
    p.add_argument("--shigapass", nargs="+", required=True, metavar="TSV",
                   help="ShigaPass report(s) from `shigella-typing shigapass`")
    p.add_argument("--mykrobe", nargs="+", required=True, metavar="TSV",
                   help="Mykrobe report(s) from `shigella-typing mykrobe`")
    p.add_argument("--outdir", required=True, help="output folder")
    p.add_argument("--strip-suffixes", action="store_true",
                   help="match sample names after removing " + ", ".join(SUFFIXES))


def main(args):
    from shigella_typing.mykrobe_tool import REPORT_COLUMNS as MY_REPORT
    from shigella_typing.shigapass_tool import REPORT_COLUMNS as SP_REPORT

    sp_rows = read_reports(args.shigapass, SP_REPORT[:14], "ShigaPass")
    my_rows = read_reports(args.mykrobe, MY_REPORT[:14], "Mykrobe")
    os.makedirs(args.outdir, exist_ok=True)
    out = os.path.join(args.outdir, "shigella_typing_report.tsv")
    rows = write_combined(out, sp_rows, my_rows, args.strip_suffixes)
    flagged = sum(1 for r in rows if re.search(r"Discordant|Missing|check", r["warnings"]))
    log(f"wrote {out} ({len(rows)} samples, {flagged} with cross-check warnings)")
    return 0
