# Galaxy test data

Public data only. Every file here is a small cut-down of a public genome or
read set; each one is listed below with its accession and source study.
Rebuild them all with `validation/make_test_data.sh`.

- **Assemblies** keep only the contigs hit by the ShigaPass databases
  (`validation/make_test_assembly.py`). ShigaPass gives the same result as
  on the full assembly.
- **ONT reads** (SRR22313045) keep only the stretches of each read around
  probe k-mer hits (100 bp either side), each as its own read. Mykrobe gives
  the same result as on the full run.
- **Reads** keep only the read pairs that share a 21-mer with a probe in the
  bundled Mykrobe panels (`validation/make_test_reads.py`). Read names are
  shortened; sequences and qualities are unchanged. Mykrobe gives the same
  result as on the full read set, including species coverage (checked in
  `validation/PHASE6.md`).

| File | Accession | Source study / BioProject | Expected result |
|---|---|---|---|
| `ERR5976293.fasta.gz` | ERR5976293 | ShigaPass `Example/` (Yassine *et al.* 2023), PRJEB44801 | ShigaPass SS (*S. sonnei*) |
| `ERR5952732.fasta.gz` | ERR5952732 | ShigaPass `Example/`, PRJEB44801 | ShigaPass SF1-5, *S. flexneri* 1b |
| `ERR5888634.fasta.gz` | ERR5888634 | ShigaPass `Example/`, PRJEB44801 | ShigaPass SB2 (*S. boydii* 2) |
| `ERR5982186.fasta.gz` | ERR5982186 | ShigaPass `Example/`, PRJEB44801 | ShigaPass SD2 (*S. dysenteriae* 2) |
| `ERR5976293_1/_2.fastq.gz` | ERR5976293 | PRJEB44801 | Mykrobe sonnei 3.7.25 (MSM4), no QRDR |
| `ERR5952732_1/_2.fastq.gz` | ERR5952732 | PRJEB44801; Flex-It (Hawkey *et al.* 2026) | Mykrobe flexneri 1.2.2.5.3, no QRDR |
| `SRR8117834_1/_2.fastq.gz` | SRR8117834 | PRJNA315192; Sonneityping (Hawkey *et al.* 2021) | Mykrobe sonnei 3.6.1.1.2, gyrA_D87G;gyrA_S83L;parC_S80I |
| `ERR047239_1/_2.fastq.gz` | ERR047239 | PRJEB2508; mykrobeshig `example_data`, Flex-It | Mykrobe flexneri 2.1.2.7, gyrA_S83L |
| `SRR4787878_1/_2.fastq.gz` | SRR4787878 | PRJNA315192; Flex-It | *E. coli*: none matched, borderline-coverage warnings |
| `SRR5306599_1/_2.fastq.gz` | SRR5306599 | PRJNA218110; Flex-It | *S. boydii*: none matched, Not E. coli/Shigella (first 2000 kept pairs only) |
| `SRR22313045.fastq.gz` | SRR22313045 | PRJNA315192 (UKHSA), Oxford Nanopore MinION | Mykrobe sonnei 3.7.25 (MSM4), no QRDR |
| `combine_*.tsv` | as above | made from the files above (and the full ERR5888634 reads) by `make_test_data.sh` | Combine Shigella report tests: concordant, discordant (`SWAP` = ERR5976293 assembly + ERR5952732 reads), no-scheme species, missing from either report |
