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
# ONT: long reads trimmed to the stretches around probe hits
python validation/make_test_reads.py panels "$out/SRR22313045" "$reads/SRR22313045.fastq.gz" --trim &
wait
mv "$out/SRR22313045_1.fastq.gz" "$out/SRR22313045.fastq.gz"

# Report inputs for the Combine Shigella report tests
tmp=$(mktemp -d)
shigella-typing shigapass --assembly "$out"/ERR5976293.fasta.gz "$out"/ERR5952732.fasta.gz \
    "$out"/ERR5888634.fasta.gz "$out"/ERR5976293.fasta.gz \
    --name ERR5976293 ERR5952732 ERR5888634 SWAP --outdir "$tmp/sp"
cp "$tmp/sp/shigapass_report.tsv" "$out/combine_shigapass_report.tsv"
for pair in ERR5976293:ERR5976293 SWAP:ERR5952732 SRR8117834:SRR8117834; do
    name=${pair%%:*}; s=${pair#*:}
    shigella-typing mykrobe --reads "$out/${s}_1.fastq.gz" "$out/${s}_2.fastq.gz" \
        --sample "$name" --outdir "$tmp/$name"
    cp "$tmp/$name/mykrobe_report.tsv" "$out/combine_mykrobe_$name.tsv"
done
# S. boydii: report from the full read set (no reads for it in test-data)
shigella-typing mykrobe --reads "$reads/ERR5888634_1.fastq.gz" "$reads/ERR5888634_2.fastq.gz" \
    --outdir "$tmp/ERR5888634"
cp "$tmp/ERR5888634/mykrobe_report.tsv" "$out/combine_mykrobe_ERR5888634.tsv"
rm -rf "$tmp"
