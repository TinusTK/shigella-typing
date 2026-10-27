#!/usr/bin/env bash
# Run Mykrobe with both Shigella schemes (sonnei and flexneri) on every run
# in accessions.tsv, as the `auto` scheme will.
#
# Output: data/results/mykrobe/<RUN>.<scheme>.json and .log (time -l stats).
#
# Usage: run_mykrobe.sh [accessions.tsv] [threads, default 4]
# Needs: mykrobe 0.13.0, panels in data/panels/panels_dir.
set -euo pipefail

here=$(cd "$(dirname "$0")" && pwd)
list=${1:-$here/accessions.tsv}
threads=${2:-4}
data=$here/data
panels=$data/panels/panels_dir
out=$data/results/mykrobe
mkdir -p "$out"
export PYTHONWARNINGS=ignore

for run in $(tail -n +2 "$list" | cut -f1); do
    r1=$data/reads/${run}_1.fastq.gz
    r2=$data/reads/${run}_2.fastq.gz
    if [ ! -s "$r1" ] || [ ! -s "$r2" ]; then
        echo "$run: no reads, skipped"
        continue
    fi
    for scheme in flexneri sonnei; do
        json=$out/$run.$scheme.json
        [ -s "$json" ] && { echo "$run $scheme: already done"; continue; }
        if /usr/bin/time -l mykrobe predict --sample "$run" --species "$scheme" \
            --skeleton_dir "$out/skeletons" \
            --panels_dir "$panels" --format json --out "$json" \
            -t "$threads" -m 2048MB --tmp "$out/tmp_$run/" \
            --seq "$r1" "$r2" > "$out/$run.$scheme.log" 2>&1; then
            echo "$run $scheme: ok $(awk '/ real /{print $1"s"}' "$out/$run.$scheme.log")"
        else
            echo "$run $scheme: FAIL (see $run.$scheme.log)"
        fi
        rm -rf "$out/tmp_$run"
    done
done
echo DONE
