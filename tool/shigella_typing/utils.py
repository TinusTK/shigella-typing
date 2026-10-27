"""Small helpers shared by the tools: logging, running programs, TSV output."""

import os
import subprocess
import sys


def log(msg):
    sys.stderr.write(f"[shigella-typing] {msg}\n")
    sys.stderr.flush()


def run(cmd, cwd=None, env=None):
    """Run a program; return (exit code, stdout, stderr). Never raises on failure."""
    try:
        res = subprocess.run(cmd, cwd=cwd, env=env, capture_output=True, text=True)
    except OSError as exc:
        return 127, "", str(exc)
    return res.returncode, res.stdout, res.stderr


def last_line(text):
    """Last non-empty line of a program's output, for short error messages."""
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    return lines[-1] if lines else ""


def sample_name_from_path(path):
    """Sample name for CLI use: file name without FASTA/FASTQ/gzip extensions."""
    name = os.path.basename(path)
    for ext in (".gz", ".bz2"):
        if name.endswith(ext):
            name = name[: -len(ext)]
    for ext in (".fasta", ".fas", ".fna", ".fa", ".fastq", ".fq", ".contigs"):
        if name.endswith(ext):
            name = name[: -len(ext)]
            break
    return name


def check_unique(names, what="sample"):
    """Exit with a clear error listing duplicate names."""
    seen, dups = set(), []
    for n in names:
        if n in seen and n not in dups:
            dups.append(n)
        seen.add(n)
    if dups:
        sys.exit(f"Error: duplicate {what} names: {', '.join(dups)}")


def clean(value):
    """Make a value safe for a TSV cell."""
    return " ".join(str(value).replace("\t", " ").split())


def write_tsv(path, columns, rows):
    with open(path, "w") as fh:
        fh.write("\t".join(columns) + "\n")
        for row in rows:
            fh.write("\t".join(clean(row.get(c, "")) for c in columns) + "\n")
