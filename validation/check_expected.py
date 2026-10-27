#!/usr/bin/env python3
"""Apply the `auto` scheme to Mykrobe JSONs and compare with published results.

For each run in accessions.tsv, reads <run>.flexneri.json and
<run>.sonnei.json, picks the scheme whose species coverage reaches the
mykrobeshig threshold (flexneri >= 85.5, sonnei >= 90; mykrobeshig rejects
only below the threshold), and compares species call, genotype and QRDR
calls with the expected values. Rules follow mykrobeshig (commit 4c7521b):
phylogroup 'Unknown' -> 'Not E. coli/Shigella'; QRDR counted only when
the drug is predicted R. Unlike mykrobeshig, QRDR is read from every drug
entry (sonnei panel: 'quinolones'), not only 'ciprofloxacin'.

Usage: check_expected.py accessions.tsv RESULTS_DIR -o concordance.tsv
Standard library only.
"""
import argparse
import csv
import json
import os

SCHEMES = {
    "flexneri": ("Shigella_flexneri", 85.5, "S. flexneri"),
    "sonnei": ("Shigella_sonnei", 90.0, "S. sonnei"),
}


def load(path):
    if not os.path.exists(path):
        return None
    with open(path) as fh:
        return next(iter(json.load(fh).values()))


def scheme_result(sample, scheme):
    """Species coverage, pass/fail, genotype and QRDR for one scheme."""
    species_key, threshold, _ = SCHEMES[scheme]
    phylo = sample["phylogenetics"]
    species = phylo.get("species", {})
    group = phylo.get("phylo_group", {})
    cov = species.get(species_key, {}).get("percent_coverage")
    res = {
        "cov": cov,
        "group_unknown": not group or "Unknown" in group,
        "pass": cov is not None and cov >= threshold,
        "genotype": "-",
        "qrdr": "-",
    }
    if res["pass"]:
        calls = phylo.get("lineage", {}).get("lineage", [])
        res["genotype"] = ";".join(c.replace("lineage", "", 1) for c in calls) or "uncalled"
        # The flexneri panel files QRDR calls under 'ciprofloxacin', the
        # sonnei panel under 'quinolones'; read every drug entry.
        found = sorted({k.split("-")[0]
                        for drug in sample.get("susceptibility", {}).values()
                        if drug.get("predict") == "R"
                        for k in drug.get("called_by", {})})
        res["qrdr"] = ";".join(found) or "none"
    return res


def auto(results):
    """The scheme/species call the `auto` mode would report."""
    passed = [s for s, r in results.items() if r and r["pass"]]
    if len(passed) == 1:
        s = passed[0]
        return s, SCHEMES[s][2], results[s]["genotype"], results[s]["qrdr"]
    if len(passed) == 2:
        return "both", "matched both schemes", "-", "-"
    if all(r and r["group_unknown"] for r in results.values()):
        return "none matched", "Not E. coli/Shigella", "-", "-"
    return "none matched", "Unknown E. coli/Shigella", "-", "-"


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("accessions")
    ap.add_argument("results_dir")
    ap.add_argument("-o", "--out", required=True)
    args = ap.parse_args()

    header = ["run", "organism", "serotype", "flexneri_species_cov", "sonnei_species_cov",
              "scheme", "species_call", "genotype", "qrdr",
              "expected_scheme", "expected_species_call", "expected_genotype", "expected_qrdr",
              "scheme_match", "species_match", "genotype_match", "qrdr_match", "result", "source"]
    rows = []
    with open(args.accessions) as fh:
        for exp in csv.DictReader(fh, delimiter="\t"):
            run = exp["run"]
            samples = {s: load(os.path.join(args.results_dir, f"{run}.{s}.json")) for s in SCHEMES}
            if not all(samples.values()):
                rows.append([run, exp["organism"], exp["serotype"]] + ["missing"] * 14
                            + ["NOT RUN", exp["source"]])
                continue
            res = {s: scheme_result(samples[s], s) for s in SCHEMES}
            scheme, species, genotype, qrdr = auto(res)

            def match(got, want):
                return "n/a" if want == "-" and got == "-" else (
                    "no ref" if want == "-" else ("yes" if got == want else "NO"))
            m = [
                "yes" if scheme == exp["expected_scheme"] or
                (exp["expected_scheme"] == "none" and scheme == "none matched") else "NO",
                match(species, exp["expected_species_call"]),
                match(genotype, exp["expected_genotype"]),
                match(qrdr, exp["expected_qrdr"]),
            ]
            result = "FAIL" if "NO" in m else "pass"
            rows.append([run, exp["organism"], exp["serotype"],
                         str(res["flexneri"]["cov"]), str(res["sonnei"]["cov"]),
                         scheme, species, genotype, qrdr,
                         exp["expected_scheme"], exp["expected_species_call"],
                         exp["expected_genotype"], exp["expected_qrdr"]] + m + [result, exp["source"]])

    with open(args.out, "w") as fh:
        for row in [header] + rows:
            fh.write("\t".join(row) + "\n")
    for r in rows:
        print(f"{r[0]:12} {r[-2]:7} {r[5]:13} {r[6]:26} {r[7]:14} {r[8]}")


if __name__ == "__main__":
    main()
