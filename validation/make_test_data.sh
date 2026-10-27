#!/usr/bin/env bash
# Rebuild tool/test-data from the full-size public data in validation/data/
# (fetch_reads.sh for reads; ShigaPass's Example/ for assemblies).
# Run from the repo root inside the shigella-typing conda environment.
set -euo pipefail

reads=validation/data/reads
asm=validation/data/shigapass_examples/in
out=tool/test-data
db=$(python -c "from shigella_typing import shigapass_tool as s; print(s.find_database(s.find_shigapass()))")

for s in ERR5976293 ERR5952732 ERR5888634 ERR5982186; do
    python validation/make_test_assembly.py "$db" "$asm/$s.fasta.gz" "$out/$s.fasta.gz"
done

for s in ERR5976293 ERR5952732 SRR8117834 ERR047239 SRR4787878; do
    python validation/make_test_reads.py panels "$out/$s" "$reads/${s}_1.fastq.gz" "$reads/${s}_2.fastq.gz" &
done
# Not E. coli/Shigella: a slice is enough
python validation/make_test_reads.py panels "$out/SRR5306599" \
    "$reads/SRR5306599_1.fastq.gz" "$reads/SRR5306599_2.fastq.gz" --max-pairs 2000 &
wait
