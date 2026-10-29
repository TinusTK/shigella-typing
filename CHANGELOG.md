# Changelog

## 1.0.1+galaxy1 (2026-10-29)

- Galaxy: the three wrappers now declare `<required_files>` (the
  `shigella_typing` package and the bundled panels), so they also run on
  remote job runners such as Pulsar. No change to the tools or results.

## 1.0.1 (2026-10-27)

- Docs: Mykrobe's `Not E. coli/Shigella` call on some *S. boydii* /
  *S. dysenteriae* is explained in the README and the Mykrobe tool help.
- Validation: 45 more public runs through all three tools, 45/45 as
  expected (`validation/PHASE0.md`, `validation/set45_*.tsv`).

## 1.0.0 (2026-10-27)

First release: three Galaxy tools and a standalone command for *Shigella*
typing.

- **ShigaPass typing** (`shigella-typing shigapass`): species and serotype
  from assemblies with ShigaPass 1.5.0; one row per assembly, always, with
  readable species / serotype and warnings. Optional *Also run Mykrobe
  genotyping* with the reads gives the combined report in one step.
- **Mykrobe Shigella genotyping** (`shigella-typing mykrobe`): *S. sonnei*
  (Sonneityping, panel 20210201) and *S. flexneri* (Flex-It, panel 20250902)
  genotypes and *gyrA* / *parC* QRDR mutations from paired, single-end or
  Nanopore reads with Mykrobe 0.13.0; `auto` scheme choice; bundled panels,
  never downloaded; graded `cipro_prediction`; borderline-coverage warning.
  Uses vendored mykrobeshig (unchanged, commit 4c7521b) for genotypes and its
  own QRDR parsing, which also reports *S. sonnei* QRDR calls.
- **Combine Shigella report** (`shigella-typing combine`): joins the two
  reports with cross-check warnings (discordant species, no Mykrobe match,
  no scheme for the species, not *Shigella*, missing samples, duplicates).
- `shigella-typing run`: all three steps from one samplesheet.
- Galaxy wrappers (profile 23.0) with planemo tests on public test data, and
  two example workflows (`workflows/`).
- Validation on public data: Mykrobe calls match published genotypes for
  19/19 read sets (`validation/PHASE0.md`); ShigaPass reproduces its own
  example results; the three routes give the same combined report
  (`validation/PHASE5.md`); resource use per sample (`validation/PHASE6.md`).
