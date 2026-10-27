#!/usr/bin/env bash
# Download Illumina paired reads for every run in accessions.tsv.
#
# Reads come from NCBI SRA's AWS open-data bucket (much faster than ENA's
# FASTQ mirror from Australia) and are converted with fasterq-dump.
# Output: data/reads/<RUN>_1.fastq.gz, <RUN>_2.fastq.gz (git-ignored).
#
# Usage: fetch_reads.sh [accessions.tsv] [parallel downloads, default 4]
# Needs: curl, fasterq-dump (sra-tools), gzip.
set -euo pipefail

here=$(cd "$(dirname "$0")" && pwd)
list=${1:-$here/accessions.tsv}
jobs=${2:-4}
data=$here/data
mkdir -p "$data/sra" "$data/reads"

fetch_one() {
    run=$1
    data=$2
    reads=$data/reads
    if [ -s "$reads/${run}_1.fastq.gz" ] && [ -s "$reads/${run}_2.fastq.gz" ]; then
        echo "$run: already present"
        return 0
    fi
    sra=$data/sra/$run.sra
    curl -sSfL --retry 3 -o "$sra.part" "https://sra-pub-run-odp.s3.amazonaws.com/sra/$run/$run" \
        && mv "$sra.part" "$sra" || { echo "$run: FAIL download"; return 1; }
    tmp=$reads/tmp_$run
    fasterq-dump --split-files -e 2 -O "$reads" -t "$tmp" "$sra" >/dev/null 2>&1 \
        || { echo "$run: FAIL fasterq-dump"; return 1; }
    rm -rf "$tmp"
    gzip -f -1 "$reads/${run}_1.fastq" "$reads/${run}_2.fastq" \
        || { echo "$run: FAIL gzip (not paired?)"; return 1; }
    echo "$run: ok $(shasum -a 256 "$sra" | cut -c1-16) $(du -m "$sra" | cut -f1) MB"
    rm -f "$sra"
}
export -f fetch_one

tail -n +2 "$list" | cut -f1 | xargs -P "$jobs" -I{} bash -c 'fetch_one "$@"' _ {} "$data"
echo DONE
