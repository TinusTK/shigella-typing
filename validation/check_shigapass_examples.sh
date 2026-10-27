#!/usr/bin/env bash
# Check tool 1 against ShigaPass's own example results.
#
# Downloads the four example assemblies and ShigaPass_summary.csv from the
# ShigaPass repository (pinned commit), runs `shigella-typing shigapass` with
# the raw summary output, and compares it line by line with upstream.
#
# Usage: check_shigapass_examples.sh [workdir]   (default: data/shigapass_examples)
# Needs: shigella-typing, ShigaPass.sh, BLAST+ (conda env from environment.yml), curl.
set -euo pipefail

here=$(cd "$(dirname "$0")" && pwd)
work=${1:-$here/data/shigapass_examples}
sha=7eb5e11bd323f21b00a8ba89864f942c579b32d5
base=https://raw.githubusercontent.com/imanyass/ShigaPass/$sha/Example
samples="ERR5888634 ERR5952732 ERR5976293 ERR5982186"

mkdir -p "$work/in"
for s in $samples; do
    [ -s "$work/in/$s.fasta.gz" ] || curl -sSfL -o "$work/in/$s.fasta.gz" "$base/Input/$s.fasta.gz"
done
curl -sSfL -o "$work/expected_summary.csv" "$base/ShigaPass_Results/ShigaPass_summary.csv"

assemblies=()
for s in $samples; do assemblies+=("$work/in/$s.fasta.gz"); done
shigella-typing shigapass --assembly "${assemblies[@]}" --outdir "$work/out" \
    --threads 4 --raw-outputs summary

if diff <(sort "$work/expected_summary.csv") <(sort "$work/out/ShigaPass_summary.csv"); then
    echo "PASS: ShigaPass summary identical to upstream example results"
else
    echo "FAIL: ShigaPass summary differs from upstream example results"
    exit 1
fi
cut -f1,9,10,12,13,14 "$work/out/shigapass_report.tsv"
