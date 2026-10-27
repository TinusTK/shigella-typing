#!/usr/bin/env python3
"""Compare Mykrobe JSON results with reference JSONs (Phase 0 validation).

Pulls the calls that matter for Shigella typing out of each Mykrobe
`predict --format json` file (species, phylogroup, lineage/genotype, every
lineage marker's genotype, QRDR variants, panel and Mykrobe version) and
writes one row per sample with the local value, the reference value and
whether they match.

Usage:
    compare_mykrobe_json.py --pair SAMPLE LOCAL.json REFERENCE.json [--pair ...] -o out.tsv

Standard library only.
"""
import argparse
import json
import sys


def load(path):
    with open(path) as fh:
        data = json.load(fh)
    if len(data) != 1:
        sys.exit(f"{path}: expected one sample, found {len(data)}")
    return next(iter(data.values()))


def best(calls):
    """Name and coverage of the highest-coverage entry, e.g. species."""
    if not calls:
        return "none", ""
    name = max(calls, key=lambda k: calls[k].get("percent_coverage", -1))
    return name, calls[name].get("percent_coverage", "")


def node_genotypes(lineage):
    """'node:marker=genotype' for every marker in the final call, sorted."""
    out = []
    for final in lineage.get("calls", {}).values():
        for node, markers in final.items():
            for marker, call in markers.items():
                gt = "/".join(str(g) for g in call.get("genotype", []))
                out.append(f"{node}:{marker}={gt}")
    return ";".join(sorted(out)) or "none"


def qrdr(susceptibility):
    """Called QRDR variants, e.g. 'gyrA_S83L' (ref/alt suffix dropped)."""
    found = set()
    for drug in susceptibility.values():
        for name in drug.get("called_by", {}):
            found.add(name.split("-")[0])
    return ";".join(sorted(found)) or "none"


def summarise(sample):
    phylo = sample.get("phylogenetics", {})
    lineage = phylo.get("lineage", {})
    species, species_cov = best(phylo.get("species", {}))
    group, group_cov = best(phylo.get("phylo_group", {}))
    summary = lineage.get("calls_summary", {})
    nodes = ";".join(
        f"{k}:{v.get('good_nodes')}/{v.get('tree_depth')}" for k, v in sorted(summary.items())
    )
    cipro = sample.get("susceptibility", {}).get("ciprofloxacin", {}).get("predict", "")
    version = sample.get("version", {})
    return {
        "species": species,
        "species_coverage": species_cov,
        "phylo_group": group,
        "phylo_group_coverage": group_cov,
        "genotype": ";".join(lineage.get("lineage", [])) or "none",
        "good_nodes": nodes or "none",
        "marker_genotypes": node_genotypes(lineage),
        "qrdr": qrdr(sample.get("susceptibility", {})),
        "cipro_predict": cipro,
        "panel": version.get("panel", ""),
        "mykrobe_version": version.get("mykrobe-predictor", ""),
    }


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--pair", nargs=3, action="append", required=True,
                    metavar=("SAMPLE", "LOCAL", "REFERENCE"))
    ap.add_argument("-o", "--out", required=True)
    args = ap.parse_args()

    fields = list(summarise({}).keys())
    header = ["sample"]
    for f in fields:
        header += [f"{f}_local", f"{f}_reference", f"{f}_match"]
    header.append("all_match")

    rows = []
    for sample, local, ref in args.pair:
        a, b = summarise(load(local)), summarise(load(ref))
        row, ok = [sample], True
        for f in fields:
            match = a[f] == b[f]
            ok &= match
            row += [str(a[f]), str(b[f]), "yes" if match else "NO"]
        row.append("yes" if ok else "NO")
        rows.append(row)
        print(f"{sample}: {'all match' if ok else 'DIFFERENCES'} "
              f"(genotype {a['genotype']} vs {b['genotype']}, QRDR {a['qrdr']} vs {b['qrdr']})")

    with open(args.out, "w") as fh:
        for row in [header] + rows:
            fh.write("\t".join(row) + "\n")


if __name__ == "__main__":
    main()
