# Phase 5: combined report

`phase5_combined_report.tsv` was made with `shigella-typing run` (2026-10-27)
from public data only:

| Sample | Assembly | Reads | Purpose |
|---|---|---|---|
| ERR5976293 | ShigaPass Example | ERR5976293 | *S. sonnei* |
| ERR5952732 | ShigaPass Example | ERR5952732 | *S. flexneri* 1b |
| ERR5888634 | ShigaPass Example | ERR5888634 | *S. boydii* 2 (no Mykrobe scheme) |
| ERR5982186 | ShigaPass Example | ERR5982186 | *S. dysenteriae* 2 (no Mykrobe scheme) |
| SWAP_sonnei_asm_flex_reads | ERR5976293 (sonnei) | ERR5952732 (flexneri) | discordant on purpose |
| NO_READS | ERR5976293 | none | missing reads |
| ECOLI_no_assembly | none | SRR4787878 (*E. coli*) | missing assembly, borderline coverage |
| NOT_SHIGELLA | random 200 kb sequence | SRR5306599 (Mykrobe: Not E. coli/Shigella) | not Shigella |

The same samples were also run as three separate tools (`shigapass`,
`mykrobe` per sample, `combine`) and as `shigapass --with-mykrobe`:

- All samples with both an assembly and reads: **identical** across all
  three routes.
- `shigapass --with-mykrobe` and `run`: **identical** for every sample.
- Samples missing one input differ only in wording, by design: the separate
  route says `Missing from Mykrobe report` / `Missing from ShigaPass report`
  (tool 3 never saw that input); the toggle and `run` say
  `Mykrobe not run: missing reads` / `ShigaPass not run: missing assembly`.

Routing in the toggle (SS → sonnei first, SF1-5 → flexneri first) only
skips the second Mykrobe run when the first scheme matches; if it does not
match, the other scheme runs too, so the call is the same as `auto` (here
12 Mykrobe runs instead of 14).
