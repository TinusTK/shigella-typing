"""
Cut a read set down to the read pairs Mykrobe actually uses: pairs where
either read shares a 21-mer (Mykrobe's k-mer size) with any probe in the
bundled panels. Mykrobe only counts probe k-mers, so the calls stay the
same while the files shrink to a few MB (checked in validation/PHASE6.md).
Read names are shortened to <sample>.<n>; sequences and qualities are kept.

Usage: python make_test_reads.py PANELS_DIR OUT_PREFIX R1.fastq.gz [R2.fastq.gz] [--max-pairs N]
Writes OUT_PREFIX_1.fastq.gz (and _2) with the kept reads, in input order;
--max-pairs stops after N kept pairs.
"""
import glob
import gzip
import os
import subprocess
import sys

K = 21
COMP = bytes.maketrans(b"ACGTN", b"TGCAN")


def revcomp(seq):
    return seq.translate(COMP)[::-1]


def probe_kmers(panels_dir):
    kmers = set()
    for fa in glob.glob(os.path.join(panels_dir, "*", "*.fa.gz")):
        with gzip.open(fa, "rb") as fh:
            seqs, cur = [], []
            for line in fh:
                if line.startswith(b">"):
                    seqs.append(b"".join(cur))
                    cur = []
                else:
                    cur.append(line.strip().upper())
            seqs.append(b"".join(cur))
        for s in seqs:
            for seq in (s, revcomp(s)):
                for i in range(len(seq) - K + 1):
                    kmers.add(seq[i:i + K])
    return kmers


def records(path):
    proc = subprocess.Popen(["gzip", "-dc", path], stdout=subprocess.PIPE)
    lines = iter(proc.stdout)
    for header in lines:
        yield header, next(lines), next(lines), next(lines)
    proc.wait()


def hits(seq, kmers):
    seq = seq.strip().upper()
    return any(seq[i:i + K] in kmers for i in range(len(seq) - K + 1))


def main():
    args = sys.argv[1:]
    max_pairs = None
    if "--max-pairs" in args:
        i = args.index("--max-pairs")
        max_pairs = int(args[i + 1])
        del args[i:i + 2]
    panels_dir, prefix, *reads = args
    name = os.path.basename(prefix)
    kmers = probe_kmers(panels_dir)
    outs = [gzip.open(f"{prefix}_{n}.fastq.gz", "wb", compresslevel=9)
            for n in range(1, len(reads) + 1)]
    total = kept = 0
    for recs in zip(*(records(r) for r in reads)):
        total += 1
        if any(hits(rec[1], kmers) for rec in recs):
            kept += 1
            for out, rec in zip(outs, recs):
                out.writelines([f"@{name}.{kept}\n".encode(), rec[1], b"+\n", rec[3]])
            if kept == max_pairs:
                break
    for out in outs:
        out.close()
    print(f"{prefix}: kept {kept} of {total} read pairs", file=sys.stderr)


if __name__ == "__main__":
    main()
