# Mykrobe panels (bundled)

This folder is a Mykrobe `--panels_dir`: the tools always run Mykrobe with
`--panels_dir panels` and never download anything at runtime.

| Species | Panel | Scheme | Source |
|---|---|---|---|
| *S. sonnei* | 20210201 | Sonneityping (Hawkey et al. 2021) | figshare 26274424 |
| *S. flexneri* | 20250902 | Flex-It (Hawkey et al. 2026) | figshare 63190870 |

Not populated yet (Phase 2). To populate:

```
mykrobe panels update_metadata --panels_dir panels
mykrobe panels update_species  --panels_dir panels sonnei
mykrobe panels update_species  --panels_dir panels flexneri
```

Sizes, checksums, licence (Mykrobe-tools/mykrobe-data, MIT) and citations go
in `SOURCES.md` when the panels are added.
