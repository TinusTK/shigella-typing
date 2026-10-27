# Phase 6: tests and resource use

## Test data

`tool/test-data/` (about 18 MB, public data only) is made from the full-size
public data by `validation/make_test_data.sh`. Accessions and expected
results are in `tool/test-data/README.md`.

- **Assemblies**: the four ShigaPass `Example/` genomes cut to the contigs
  the ShigaPass databases hit (25-29 contigs, about 0.4 Mb each). ShigaPass
  gives an identical report on the cut and full assemblies.
- **Reads**: six read sets cut to the pairs sharing a 21-mer with a panel
  probe (about 1% of pairs). Mykrobe gives an identical report on the cut
  and full reads for all six, including species coverage, QRDR calls,
  confidence and the borderline-coverage warnings. SRR5306599 (Not E.
  coli/Shigella) keeps only its first 2000 such pairs.

## Tests

`python -m unittest discover -s tests` runs 56 tests in about 30 s; none
are skipped in the conda environment. The end-to-end tests
(`tests/test_end_to_end.py`) cover:

- tool 1 on four assemblies (SS, SF1-5 1b, SB2, SD2);
- tool 2 on paired reads (sonnei triple QRDR mutant, flexneri gyrA_S83L),
  single-end reads with a manual scheme, and a borderline *E. coli*;
- `run` with samples that have both inputs, only an assembly and only reads;
- the three tools chained, and the tool 1 toggle, give the same rows as `run`.

CI runs them in a job with the conda environment and fails if any test
is skipped. ONT reads are not in the test data yet (no public ONT
*Shigella* run has been cut down); Phase 7 adds one for the Galaxy tests.

## Resource use per sample

Measured with `validation/measure_resources.sh` (results in
`resources.tsv`) on full-size public data, one command at a time, on an
Apple M2 (8 cores, 8 GB RAM, local SSD). CPU time includes child processes
(BLAST, Mykrobe, gzip). Peak memory is the largest single process.

| Tool | Input | Threads | Wall time | CPU time | Peak memory |
|---|---|---|---|---|---|
| 1 ShigaPass | one assembly (4.4-4.8 Mb) | 1 | 10-12 s | 10-12 s | 115-130 MB |
| 1 ShigaPass | one assembly | 4 | 8-9 s | 11 s | 115-130 MB |
| 2 Mykrobe (`auto`, both schemes) | ERR5952732, 2.2 M pairs, 470 MB gz | 1 | 53-54 s | 89-91 s | 67 MB |
| | | 2 | 25 s | 72 s | 66 MB |
| | | 4 | 12.5 s | 62 s | 67 MB |
| 2 Mykrobe (`auto`) | SRR4787878, 0.9 M pairs, 140 MB gz | 2 | 9 s | 24 s | 67 MB |
| | SRR8117834, 1.3 M pairs, 190 MB gz | 2 | 12 s | 33 s | 67 MB |
| | ERR5976293, 2.0 M pairs, 430 MB gz | 2 | 24 s | 67 s | 66 MB |
| | ERR047239, 4.9 M pairs, 674 MB gz | 2 | 31 s | 89 s | 66 MB |
| 3 Combine | 4 + 5 reports | 1 | < 0.1 s | < 0.1 s | 15 MB |

Peak memory for Mykrobe was checked with `/usr/bin/time -l` as well (70 MB).
Mykrobe's `-m 2048MB` reserves a hash table it mostly does not touch here.

Suggested Galaxy Australia allocation (per job, before Galaxy's own
staging time; Linux nodes may be slower than this laptop):

- **Tool 1**: 1 core, 1 GB. About 10 s per assembly; more threads barely help.
  Runtime grows with the number of contigs: 45 Shovill assemblies (860 to
  6374 contigs each, many under 500 bp) took 14 min in one job with 4
  threads, about 19 s per assembly on average and over a minute for the
  most fragmented ones.
- **Tool 2**: 2-4 cores, 2 GB (matches `--memory 2048MB`). About 10-30 s
  per sample with 2 threads; scales well to 4.
- **Tool 1 with the Mykrobe toggle / `run`**: as tool 2, times the number of
  samples (samples run one after another).
- **Tool 3**: 1 core, 512 MB.
