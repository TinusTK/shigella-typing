#!/usr/bin/env bash
# CPU, RAM and runtime per sample for each tool, on full-size public data
# (for Galaxy Australia). One command at a time so runs don't compete.
# Run from the repo root inside the shigella-typing conda environment.
# Writes validation/resources.tsv; summary in validation/PHASE6.md.
set -euo pipefail

reads=validation/data/reads
asm=validation/data/shigapass_examples/in
work=${TMPDIR:-/tmp}/st-resources
tsv=validation/resources.tsv
m() { python validation/measure_resources.py "$1" "$tsv" -- "${@:2}"; }

rm -rf "$work" "$tsv"
mkdir -p "$work"

# Tool 1: ShigaPass, one assembly per run
for t in 1 4; do
    for s in ERR5976293 ERR5952732 ERR5888634 ERR5982186; do
        m "shigapass $s threads=$t" shigella-typing shigapass --assembly "$asm/$s.fasta.gz" \
            --outdir "$work/sp_${s}_$t" --threads "$t"
    done
done

# Tool 2: Mykrobe, auto scheme (both schemes), paired reads
for t in 1 2 4; do
    m "mykrobe ERR5952732 threads=$t" shigella-typing mykrobe \
        --reads "$reads/ERR5952732_1.fastq.gz" "$reads/ERR5952732_2.fastq.gz" \
        --outdir "$work/my${t}_ERR5952732" --threads "$t"
done
for s in SRR4787878 SRR8117834 ERR5976293 ERR047239; do
    m "mykrobe $s threads=2" shigella-typing mykrobe \
        --reads "$reads/${s}_1.fastq.gz" "$reads/${s}_2.fastq.gz" \
        --outdir "$work/my2_$s" --threads 2
done

# Tool 3: combine the reports above
m "combine 4+5 reports" shigella-typing combine \
    --shigapass "$work"/sp_*_4/shigapass_report.tsv --mykrobe "$work"/my2_*/mykrobe_report.tsv \
    --outdir "$work/combined"

rm -rf "$work"
