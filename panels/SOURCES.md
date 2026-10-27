# Panel sources

Populated 2026-10-27 with Mykrobe 0.13.0:

```
mykrobe panels update_metadata --panels_dir panels
mykrobe panels update_species  --panels_dir panels sonnei
mykrobe panels update_species  --panels_dir panels flexneri
```

The folder is kept exactly as Mykrobe writes it (tarballs removed by
Mykrobe). The root `manifest.json` also lists other species (tb, staph,
typhi, paratyphiB); they are not installed and are never used.

## Panels

| Species | Panel | Size | Source tarball | Tarball sha256 |
|---|---|---|---|---|
| *S. sonnei* | 20210201 | 60 KB | https://ndownloader.figshare.com/files/26274424 (18,339 bytes) | `7dec81c74485e4bcc114a9722d136e1d6710d6496b6f62c6b5b1902e2b98d1f9` |
| *S. flexneri* | 20250902 | 52 KB | https://ndownloader.figshare.com/files/63190870 (17,430 bytes) | `2a070cde2c7d3b49de667bea86535cae4298e9d5dd78d9dc3d3f478c9afbed07` |

Total 120 KB. The sonnei folder also holds the 20201007 lineage files
(panel 20201012), which the 20210201 tarball ships alongside; Mykrobe uses
20210201 by default.

Panel list: `mykrobe_panels_manifest.json` in
[Mykrobe-tools/mykrobe-data](https://github.com/Mykrobe-tools/mykrobe-data)
(MIT licence). Tarballs are hosted on figshare.

## File checksums (sha256)

```
b12b80aa23e5d736bb5942224d52acf808cdc42f315f9fd7dbc2c573d74c9f6a  flexneri/flexneri.amr.20250902.json
ccd6a9283330e44a65cb1a26fe4a59065dcbe9923f1290f77e796a9ce724a729  flexneri/flexneri.amr.20250902.probes.fa.gz
c5453bcfd9587367a921a17b007efbf8c1459a6fac3a8d68ff246c69c714a13b  flexneri/flexneri.lineage.20241210.json
412c8fd4ff8bbd049de8291d8945c007f3ef2c6c0781dfa15eefe35f2f5aeef0  flexneri/flexneri.lineage.20241210.probes.fa.gz
345a09bc5dfa61ba3f70fa465d5e5045653de2af890cc07f35fffd883ad0fed4  flexneri/flexneri.mlst.20240308.fa.gz
06a0cb59a4a43b3ffadc6c55ee09b8f94fda0b6202c234bdf5fc53368dd13e7f  flexneri/manifest.json
b79994e51ac779677abbbb9ad46b0faebe1c4e350701ba433fa29da125c7c9b1  flexneri/shigella.probe.uidA.20240308.fa.gz
a92e8ecc607c88441ce02dc47d9ed6c865ddea28310b8ece75fe2abc83a608a3  sonnei/manifest.json
5999411067d7c620f8525e8a4e5c31456a4dcfcef741f927facec8541a7bcbd5  sonnei/sonnei.lineage.20201007.json
e5e8ee6741b27b3ce7598951906d211ecb9a5a61e5b4866d06d58a24438696e8  sonnei/sonnei.lineage.20201007.probes.fa.gz
59a5b48ee74fe9264adccc7e8f26f2ac7829f78f2a257ea6fb16161ec93f1d83  sonnei/sonnei.lineage.20210201.json
dc5989b86e1b57cd3655cef7e1f91d5250c4a44457d066aa4d433a3c54410fb5  sonnei/sonnei.lineage.20210201.probes.fa.gz
c2f1a40fa76b536abed2e228b773183419f9331439f6efb40ec8a9945e8168f8  sonnei/sonnei.mlst.20201010.sonnei.fa.gz
d324c0a5c2c7a0b67385f783ad6a67ed3cfa391d70f5ddda907d2203b2a9440e  sonnei/sonnei.probe.uidA.20201010.fa.gz
3d9870dda4ba9b094c670196f6d538f9a850319bcbc35e982d60344c00b7350c  sonnei/sonnei.qrdr.20201010.probes.fa.gz
347eaf987ed929023596d134edf39a3d915bfd652dfda1ee7824c56356dbd8c5  sonnei/sonnei.qrdr.20201010.res_to_drug.json
```

These are identical to the panel files validated in `validation/PHASE0.md`.

## Citations

- *S. sonnei* (Sonneityping): Hawkey J, *et al.* Global population structure
  and genotyping framework for genomic surveillance of the major dysentery
  pathogen, *Shigella sonnei*. *Nat Commun* 2021;12:2684.
  doi:10.1038/s41467-021-22700-4
- *S. flexneri* (Flex-It): Hawkey J, Nodari CS, Iqbal Z, Hunt M, Wick RR,
  Chong CE, Jenkins C, Howden BP, Holt KE, Weill F-X, Baker KS, Ingle DJ.
  Flex-It: a global standardised genotyping framework for *Shigella
  flexneri*. *bioRxiv* 2026. doi:10.64898/2026.04.17.719127 (preprint;
  replace with the journal version when published)
- Mykrobe: Hunt M, *et al.* *Wellcome Open Res* 2019;4:191.
  doi:10.12688/wellcomeopenres.15603.1
