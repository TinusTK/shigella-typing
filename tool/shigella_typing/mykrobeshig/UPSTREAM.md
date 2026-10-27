# Vendored mykrobeshig

- Upstream: https://github.com/ShigellaGenomics/mykrobeshig
- Commit: `4c7521b9fa84f931bf86e39c14cc6f2880a45775` (2026-09-17)
- Author: Jane Hawkey (ShigellaGenomics); adapted from
  [sonneityping](https://github.com/katholt/sonneityping) by Kat Holt and
  Jane Hawkey.
- Licence: GPL-3.0 (`LICENSE`, copied unchanged).

## Files

Copied byte-for-byte (git blob hashes match upstream):

| File | Upstream path |
|---|---|
| `__init__.py` | `mykrobeshig/__init__.py` |
| `parser.py` | `mykrobeshig/parser.py` |
| `data/__init__.py` | `mykrobeshig/data/__init__.py` |
| `data/alleles_sonnei.txt` | `mykrobeshig/data/alleles_sonnei.txt` |
| `LICENSE` | `LICENSE` |

**No local changes.** shigella-typing runs `parser.py` as its own program
(`python -m mykrobeshig.parser`, with this folder's parent on `PYTHONPATH`)
and reads its `predictResults.tsv`. `tests/test_mykrobe.py` checks that it
still reproduces upstream's `example_data/example_output_predictResults.tsv`
exactly.

## What shigella-typing does differently

- **QRDR calls** are read from the Mykrobe JSON by shigella-typing itself,
  not taken from mykrobeshig. At this commit mykrobeshig reads only
  `susceptibility.ciprofloxacin`; the *S. sonnei* panel (20210201) files its
  QRDR calls under `susceptibility.quinolones`, so mykrobeshig reports
  `num QRDR = NA` for every *S. sonnei* sample. It also only reports six
  named mutations, while the *S. flexneri* panel can call others (e.g.
  gyrA S83F, D87V; parC S80R).
- **Genotype**: the `lineage` prefix mykrobeshig keeps for *S. sonnei*
  (`lineage3.6.1.1.2`) is removed, matching *S. flexneri* and the published
  genotype tables.
- Genotype, genotype name, confidence, species call and marker-support
  columns are taken from mykrobeshig unchanged.

## Updating

Replace the files above with the new upstream versions, update the commit
here and in `upstream_versions.yml`, and run the tests.
