"""
Cut an assembly down to the contigs ShigaPass actually uses: contigs hit
(blastn, loose settings) by any sequence in the ShigaPass databases. The
ShigaPass call stays the same while the file shrinks (checked in PHASE6.md).

Usage: python make_test_assembly.py SHIGAPASS_DB IN.fasta[.gz] OUT.fasta.gz
Needs blastn on PATH.
"""
import glob
import gzip
import os
import subprocess
import sys
import tempfile


def read_fasta(path):
    opener = gzip.open if path.endswith(".gz") else open
    with opener(path, "rt") as fh:
        name, seq = None, []
        for line in fh:
            if line.startswith(">"):
                if name:
                    yield name, "".join(seq)
                name, seq = line[1:].split()[0], []
            else:
                seq.append(line.strip())
        if name:
            yield name, "".join(seq)


def main():
    db, inp, out = sys.argv[1:]
    contigs = list(read_fasta(inp))
    hit = set()
    with tempfile.TemporaryDirectory() as tmp:
        subject = os.path.join(tmp, "asm.fasta")
        with open(subject, "w") as fh:
            for name, seq in contigs:
                fh.write(f">{name}\n{seq}\n")
        for query in sorted(glob.glob(os.path.join(db, "*", "*.fasta"))):
            res = subprocess.run(["blastn", "-query", query, "-subject", subject,
                                  "-evalue", "1e-5", "-outfmt", "6 sseqid"],
                                 capture_output=True, text=True, check=True)
            hit.update(res.stdout.split())
    kept = [(n, s) for n, s in contigs if n in hit]
    with gzip.open(out, "wt", compresslevel=9) as fh:
        for name, seq in kept:
            fh.write(f">{name}\n")
            for i in range(0, len(seq), 80):
                fh.write(seq[i:i + 80] + "\n")
    print(f"{out}: kept {len(kept)} of {len(contigs)} contigs, "
          f"{sum(len(s) for _, s in kept)} of {sum(len(s) for _, s in contigs)} bp",
          file=sys.stderr)


if __name__ == "__main__":
    main()
