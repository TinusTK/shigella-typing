# Galaxy *Shigella* Typing Tools

> **Work in progress.** Not ready for use yet.

Three tools, usable in Galaxy or as a standalone command (`shigella-typing`),
that answer for each isolate:

1. **Is it *Shigella* / EIEC, and which serotype?** ShigaPass on the assembly.
2. **Which genotype (*S. sonnei* or *S. flexneri*)?** Mykrobe with the
   Sonneityping and Flex-It panels on the reads.
3. **Any ciprofloxacin-resistance (QRDR) mutations in *gyrA* / *parC*?**
   Mykrobe on the reads. These are genotypic markers, not a replacement for
   antimicrobial susceptibility testing.

| Tool | Input | Output |
|---|---|---|
| ShigaPass typing | Assemblies (FASTA) | ShigaPass report (optionally the combined report) |
| Mykrobe Shigella genotyping | Reads (paired, single-end or ONT) | Mykrobe report |
| Combine Shigella report | Reports from the two tools above | Combined report with cross-check warnings |

The tools are for *Shigella* only. For *M. tuberculosis* use TB-Profiler;
for other Mykrobe species use the IUC `mykrobe_predict` tool.

## Validation

Mykrobe 0.13.0 with the bundled panels was checked against published
genotypes for 19 public read sets: see [`validation/PHASE0.md`](validation/PHASE0.md).
Resource use per sample (CPU, memory, runtime) is in
[`validation/PHASE6.md`](validation/PHASE6.md).

## Tests

```
python -m unittest discover -s tests -v
```

Unit tests need only Python. The end-to-end tests run every tool, the three
tools chained, the tool 1 toggle and `run` on the small public test data in
`tool/test-data/` (cut-down assemblies and reads that give the same results
as the full data); they need the conda environment and are skipped without
it. CI runs both.

## Repository layout

```
tool/                    Galaxy wrappers, test-data and the Python package
  shigella_typing/       shared code for the CLI and the Galaxy tools
  test-data/             public test data only
panels/                  bundled Mykrobe panels (sonnei, flexneri)
scripts/bundle_tool.sh   assembles build/shigella_typing/ for Galaxy / the Tool Shed
tests/                   unit and end-to-end tests (python -m unittest discover -s tests)
validation/              validation scripts, expected results and write-up
upstream_versions.yml    every upstream version pin
environment.yml          conda environment for standalone use
```

## Running without Galaxy

```
conda env create -f environment.yml
conda activate shigella-typing
pip install -e .        # from a clone, so the bundled panels/ are found
shigella-typing --version
```

### ShigaPass typing (assemblies)

```
shigella-typing shigapass --assembly A.fasta B.fasta.gz --outdir out/ [--threads 4] \
    [--name A B] [--raw-outputs summary flex_summary]
```

Writes `out/shigapass_report.tsv`, one row per assembly (always, even if
ShigaPass fails on one: the reason goes in `warnings`). Sample names are the
file names without extensions unless `--name` is given. Columns: ShigaPass's
own fields (`rfb`, `rfb_hits`, `rfb_pct`, `mlst_st`, `fliC`, `crispr`,
`ipaH`, `predicted_serotype`, `predicted_flexserotype`, `comments`), readable
`species_shigapass` / `serotype_shigapass`, `warnings`, and versions.
`--raw-outputs` also writes ShigaPass's `ShigaPass_summary.csv` /
`ShigaPass_Flex_summary.csv` (sample names restored).

On macOS ShigaPass needs the GNU tools in `environment.yml`.

### Mykrobe Shigella genotyping (reads)

```
shigella-typing mykrobe --reads S1_R1.fastq.gz S1_R2.fastq.gz --sample S1 --outdir out/ \
    [--scheme auto|sonnei|flexneri] [--ont] [--threads 4] [--raw-outputs json predictresults]
```

One sample per run (paired, single-end, or `--ont`). Writes
`out/mykrobe_report.tsv` (one row, always). `auto` runs both schemes and
keeps the one whose species coverage reaches the mykrobeshig threshold
(*S. sonnei* 90, *S. flexneri* 85.5); otherwise `none matched` with
Mykrobe's species call (`Unknown E. coli/Shigella` or `Not E. coli/Shigella`).
QRDR mutations (`qrdr_mutations`, `num_qrdr`) are genotypic markers;
`cipro_prediction` is `no QRDR mutations`, `QRDR mutation(s): reduced
susceptibility likely` (1-2) or `QRDR triple mutant: resistance likely` (3+),
and is not a replacement for AST. A warning is added when species coverage
is within 1 point of a threshold.

Uses the bundled `panels/` (install with `pip install -e .` from a clone, or
point `--panels-dir` / `SHIGELLA_TYPING_PANELS` at them). Never downloads.

### Combine Shigella report

```
shigella-typing combine --shigapass out/shigapass_report.tsv \
    --mykrobe out/*/mykrobe_report.tsv --outdir out/ [--strip-suffixes]
```

Joins the reports on `sample` (exact match; `--strip-suffixes` also ignores
`.fasta`, `_contigs`, ...) and writes `out/shigella_typing_report.tsv`:
ShigaPass columns, Mykrobe columns, one `warnings` column and versions.
Cross-check warnings:

| Situation | Warning |
|---|---|
| ShigaPass *S. sonnei*, Mykrobe *S. flexneri* (or the reverse) | `Discordant: ShigaPass <call>, Mykrobe <species> - check` |
| ShigaPass *S. sonnei* / *S. flexneri* 1-5, Mykrobe none matched | `ShigaPass <call> but Mykrobe did not match the <scheme> scheme - check reads/assembly` |
| ShigaPass Not Shigella/EIEC, Mykrobe *S. sonnei* / *S. flexneri* | `Discordant: ShigaPass Not Shigella/EIEC, Mykrobe <species> - check assembly` |
| ShigaPass *S. boydii*, *S. dysenteriae*, *S. flexneri* 6 or EIEC, Mykrobe none matched | `No Mykrobe genotyping scheme for <species>; serotype only` (expected) |
| ShigaPass Not Shigella/EIEC and Mykrobe Not E. coli/Shigella | `Not Shigella - check organism` |
| Sample in one report only | `Missing from Mykrobe report` / `Missing from ShigaPass report` |
| Duplicate sample names | error listing the duplicates |

### All in one

```
shigella-typing shigapass --assembly A.fasta B.fasta --outdir out/ \
    --with-mykrobe --reads-samplesheet reads.tsv        # reads.tsv: sample, r1, r2
shigella-typing run --samplesheet samples.tsv --outdir out/   # sample, assembly, r1, r2
```

Both write the ShigaPass, Mykrobe and combined reports. Assemblies and reads
are matched by sample name; a sample with only one of them still gets a row.
Mykrobe tries the scheme matching the ShigaPass call first and runs the
other one too if it does not match, so the result is the same as running
the three tools separately (`validation/PHASE5.md`).

## Software and data used

Please cite these if you use the tools:

- **ShigaPass**: Yassine I, *et al.* ShigaPass: an *in silico* tool predicting
  *Shigella* serotypes from whole-genome sequencing assemblies. *Microb Genom*
  2023. [doi:10.1099/mgen.0.000961](https://doi.org/10.1099/mgen.0.000961).
  GPL-3.0, [imanyass/ShigaPass](https://github.com/imanyass/ShigaPass).
- **BLAST+**: Camacho C, *et al.* BLAST+: architecture and applications.
  *BMC Bioinformatics* 2009;10:421.
  [doi:10.1186/1471-2105-10-421](https://doi.org/10.1186/1471-2105-10-421).
- **Mykrobe**: Hunt M, *et al.* Antibiotic resistance prediction for
  *Mycobacterium tuberculosis* from genome sequence data with Mykrobe.
  *Wellcome Open Res* 2019;4:191.
  [doi:10.12688/wellcomeopenres.15603.1](https://doi.org/10.12688/wellcomeopenres.15603.1).
  MIT, [Mykrobe-tools/mykrobe](https://github.com/Mykrobe-tools/mykrobe).
- **Sonneityping** (*S. sonnei* panel): Hawkey J, *et al.* Global population
  structure and genotyping framework for genomic surveillance of the major
  dysentery pathogen, *Shigella sonnei*. *Nat Commun* 2021;12:2684.
  [doi:10.1038/s41467-021-22700-4](https://doi.org/10.1038/s41467-021-22700-4).
- **Flex-It** (*S. flexneri* panel): Hawkey J, Nodari CS, Iqbal Z, Hunt M,
  Wick RR, Chong CE, Jenkins C, Howden BP, Holt KE, Weill F-X, Baker KS,
  Ingle DJ. Flex-It: a global standardised genotyping framework for *Shigella
  flexneri*. *bioRxiv* 2026.
  [doi:10.64898/2026.04.17.719127](https://doi.org/10.64898/2026.04.17.719127).
- **mykrobeshig**: [ShigellaGenomics/mykrobeshig](https://github.com/ShigellaGenomics/mykrobeshig)
  (GPL-3.0), adapted from [sonneityping](https://github.com/katholt/sonneityping).
  Vendored in this repository.
- **Mykrobe panel data**: [Mykrobe-tools/mykrobe-data](https://github.com/Mykrobe-tools/mykrobe-data) (MIT).
- **Bioconda**: Grüning B, *et al.* *Nat Methods* 2018;15:475–476.
  [doi:10.1038/s41592-018-0046-7](https://doi.org/10.1038/s41592-018-0046-7).
- **Galaxy** and **Galaxy Australia**: citation to be added.

## Licence

GPL-3.0 (see [LICENSE](LICENSE)); it includes GPL-3.0 code from mykrobeshig.
