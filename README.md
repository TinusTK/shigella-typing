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

## Repository layout

```
tool/                    Galaxy wrappers, test-data and the Python package
  shigella_typing/       shared code for the CLI and the Galaxy tools
  test-data/             public test data only
panels/                  bundled Mykrobe panels (sonnei, flexneri)
scripts/bundle_tool.sh   assembles build/shigella_typing/ for Galaxy / the Tool Shed
tests/                   unit tests (python -m unittest discover -s tests)
validation/              validation scripts, expected results and write-up
upstream_versions.yml    every upstream version pin
environment.yml          conda environment for standalone use
```

## Running without Galaxy

```
conda env create -f environment.yml
conda activate shigella-typing
pip install .
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
