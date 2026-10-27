# Changelog

## Unreleased

- `shigella-typing shigapass` (tool 1): ShigaPass typing of assemblies,
  one isolated ShigaPass run per sample, `shigapass_report.tsv` with
  readable species/serotype and warnings; reproduces ShigaPass's example
  results (`validation/check_shigapass_examples.sh`).
- `shigella-typing mykrobe` (tool 2): Mykrobe on reads with the bundled
  panels, `auto` scheme choice, vendored mykrobeshig (unchanged, commit
  4c7521b) for genotype and confidence, own QRDR parsing (fixes missing
  S. sonnei QRDR calls), graded `cipro_prediction`, borderline-coverage
  warning. 19/19 public validation samples match published results.
- Bundled Mykrobe panels (sonnei 20210201, flexneri 20250902).

- Repository scaffold: package, CLI skeleton, unit tests, CI, bundling script.
- Phase 0 validation of Mykrobe 0.13.0 on 19 public read sets
  (`validation/PHASE0.md`).
