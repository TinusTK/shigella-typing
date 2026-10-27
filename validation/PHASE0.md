# Phase 0: Mykrobe 0.13.0 on reads

Status: **public set 19/19 pass** (2026-10-27). Own isolates (D7) still to do.

## Public validation set (19 runs)

`accessions.tsv` lists each run with its published expected result;
`fetch_reads.sh` downloads them, `run_mykrobe.sh` runs both schemes on each,
`check_expected.py` applies the `auto` rule and writes `concordance.tsv`.

| Group | Runs | Result |
|---|---|---|
| *S. flexneri* (PG1, 2, 3, 7; serotypes 1b, 1c, 2a, 3a, 4av, 5b, Y) | 8 | 8/8 scheme, genotype and QRDR match Flex-It (Hawkey 2026) |
| *S. sonnei* (lineages I, II, III incl. CipR.MSM5, VN2.MSM2.Aus) | 5 | 4/4 genotype + QRDR match Hawkey 2021; ERR5976293 → 3.7.25 (no published genotype) |
| *E. coli*, *S. flexneri* 6, *S. boydii*, *S. dysenteriae* | 6 | 6/6 none matched; species call matches Flex-It media-6 where published |

QRDR mutants confirmed: gyrA S83L, S83A, D87N, D87G; parC S80I (single,
double and triple). `auto` never matched both schemes.

Runtime: 1.6–8.2 s wall per sample per scheme (median 3.6 s), max RSS 71 MB
(4 threads, Apple M-series).

### Findings from the public set

4. **Sonnei QRDR is filed under `quinolones`, flexneri under
   `ciprofloxacin`** (panel `res_to_drug` JSONs). mykrobeshig (4c7521b) reads
   only `susceptibility.ciprofloxacin`, so from its code it would report QRDR
   = NA for every sonnei sample with panel 20210201. Not run (install was
   blocked), so confirm in Phase 4; likely worth an upstream issue. Our parser
   must read every drug entry.
5. **The flexneri panel calls more QRDR variants than mykrobeshig's fixed list
   of six** (also gyrA S83F, D87V; parC S80R; X = any). `qrdr_mutations` should
   list whatever Mykrobe calls, not just the six.
6. **Thresholds sit close to E. coli.** E. coli SRR4787878 scores 85.048 on
   flexneri (threshold 85.5) and 89.474 on sonnei (threshold 90); true
   flexneri score 87.3–88.5, true sonnei 94.6–95.2. A "species coverage
   within ~1 point of the threshold" warning would be useful.
7. **Boydii/dysenteriae can come out as `Not E. coli/Shigella`** (phylogroup
   Unknown), not only `Unknown E. coli/Shigella`. The combine warnings must
   accept both for SB/SD/SF6.
8. mykrobeshig passes a sample at coverage **≥** threshold (it rejects
   `< 85.5` / `< 90`); the plan says `>`. Follow mykrobeshig.

## Setup (2026-10-27, macOS arm64)

- Mykrobe **0.13.0** from bioconda (osx-arm64 build), Python 3.12.
  Needs **`setuptools<81`**: Mykrobe imports `pkg_resources`, which newer
  setuptools no longer ships. Pin this in `environment.yml`.
- Panels set up with Mykrobe's own commands (these are the Phase 2 commands):
  ```
  mykrobe panels update_metadata --panels_dir PANELS
  mykrobe panels update_species  --panels_dir PANELS flexneri
  mykrobe panels update_species  --panels_dir PANELS sonnei
  ```
  Result: flexneri 20250902 (52 KB), sonnei 20210201 (60 KB, also keeps
  20201012/20201007 files), manifest 4 KB; 116 KB in total. Flexneri
  tarball sha256 `2a070cde2c7d3b49de667bea86535cae4298e9d5dd78d9dc3d3f478c9afbed07`.
- Reads: NCBI SRA original files from the AWS open-data bucket
  (`sra-pub-run-odp`), converted with `fasterq-dump --split-files`
  (sra-tools 3.4.1). ENA's FASTQ mirror ran at ~33 KB/s from here.

## Runs

```
mykrobe predict --sample S --species flexneri --panels_dir PANELS \
  --format json --out S.flexneri.json -t 4 -m 2048MB --seq S_1.fastq.gz S_2.fastq.gz
```

| Sample | Scheme | Species cov. | Genotype | QRDR | Reference | Match |
|---|---|---|---|---|---|---|
| ERR047239 | flexneri | 88.23 (>85.5) | 2.1.2.7 | gyrA_S83L | 2.1.2.7, gyrA_S83L | ✅ all fields |
| SRR7223147 | flexneri | 88.463 (>85.5) | 1.2.2.5.6 | none | 1.2.2.5.6, none | ✅ all fields |
| ERR047239 | sonnei | 79.083 (<90) | rejected | – | not sonnei | ✅ |
| SRR7223147 | sonnei | 77.196 (<90) | rejected | – | not sonnei | ✅ |

Reference = mykrobeshig's `example_data/*.json` (commit 4c7521b), made with
the same Mykrobe 0.13.0 + flexneri 20250902. `compare_mykrobe_json.py`
checks species, phylogroup, lineage, good nodes, every lineage marker's
genotype, QRDR calls, cipro prediction, panel and Mykrobe version: all
identical, including coverage values to three decimals.

Runtime: 4–7 s wall, ~70 MB max RSS per sample per scheme (4 threads,
~2.5–4.9 M read pairs). `auto` (both schemes) is therefore ~2× that.

## Findings for the build

1. **Ignore the lineage when the species threshold fails.** Running the sonnei
   scheme on flexneri reads still writes a sonnei lineage (`lineage2.8.2`)
   into the JSON. `auto` must decide on species coverage only and drop
   genotype/QRDR from a failed scheme.
2. **Flexneri headroom is small**: both flexneri samples sit at ~88% against
   the 85.5 threshold. Watch for borderline flexneri samples in the wider set
   (low depth, assembly-derived input).
3. Mykrobe JSON keys used: `phylogenetics.species`, `.phylo_group`,
   `.lineage.lineage`, `.lineage.calls_summary`, `.lineage.calls`,
   `susceptibility.ciprofloxacin.called_by`, `version.panel`.
