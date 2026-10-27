"""
Unit tests for tool 2 (Mykrobe Shigella genotyping).

Uses Mykrobe JSON results from public reads (tests/data/README.md), so the
scheme choice, QRDR parsing and vendored mykrobeshig are tested without
Mykrobe. The end-to-end test runs only when mykrobe is on PATH; the full
read-level check is validation/ (19 public samples).

Run: python -m unittest discover -s tests -v
"""
import csv
import os
import random
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TOOL = os.path.join(ROOT, "tool")
DATA = os.path.join(ROOT, "tests", "data")
sys.path.insert(0, TOOL)

from shigella_typing import mykrobe_tool as mt  # noqa: E402

HAVE_MYKROBE = shutil.which("mykrobe") is not None


def results_for(run, tmp, schemes=("sonnei", "flexneri")):
    """Per-scheme results as genotype_reads builds them, from stored JSONs."""
    jsons = [os.path.join(DATA, "mykrobe_json", f"{run}.{s}.json") for s in schemes]
    rows, tsv, error = mt.run_mykrobeshig(jsons, os.path.join(tmp, "msh"))
    assert error is None, error
    return {s: {"json": mt.load_json(j), "msh": rows.get((run, s)), "error": None}
            for s, j in zip(schemes, jsons)}


class TestVendoredMykrobeshig(unittest.TestCase):
    def test_reproduces_upstream_example_exactly(self):
        tmp = tempfile.mkdtemp()
        try:
            ex = os.path.join(DATA, "mykrobeshig_example")
            _, tsv, error = mt.run_mykrobeshig(
                [os.path.join(ex, "ERR047239.json"), os.path.join(ex, "SRR7223147.json")],
                os.path.join(tmp, "example_output"))
            self.assertIsNone(error)
            with open(tsv) as a, open(os.path.join(ex, "example_output_predictResults.tsv")) as b:
                self.assertEqual(a.read(), b.read())
        finally:
            shutil.rmtree(tmp)


class TestQrdr(unittest.TestCase):
    def test_sonnei_quinolones_entry(self):
        js = mt.load_json(os.path.join(DATA, "mykrobe_json", "SRR8117834.sonnei.json"))
        self.assertIn("quinolones", js["susceptibility"])
        self.assertEqual(mt.qrdr_calls(js), ["gyrA_D87G", "gyrA_S83L", "parC_S80I"])

    def test_flexneri_ciprofloxacin_entry(self):
        js = mt.load_json(os.path.join(DATA, "mykrobe_json", "SRR4192076.flexneri.json"))
        self.assertEqual(mt.qrdr_calls(js), ["gyrA_D87N", "gyrA_S83L", "parC_S80I"])

    def test_susceptible_and_any_mutation_name(self):
        self.assertEqual(mt.qrdr_calls({"susceptibility": {"ciprofloxacin": {"predict": "S"}}}), [])
        js = {"susceptibility": {"ciprofloxacin": {"predict": "R", "called_by": {
            "gyrA_S83F-TCG1AAA": {}, "parC_S80R-AGC2CGC": {}}}}}
        self.assertEqual(mt.qrdr_calls(js), ["gyrA_S83F", "parC_S80R"])

    def test_cipro_prediction(self):
        self.assertEqual(mt.cipro_prediction(0), "no QRDR mutations")
        self.assertEqual(mt.cipro_prediction(1), "QRDR mutation(s): reduced susceptibility likely")
        self.assertEqual(mt.cipro_prediction(2), "QRDR mutation(s): reduced susceptibility likely")
        self.assertEqual(mt.cipro_prediction(3), "QRDR triple mutant: resistance likely")


class TestDecide(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def test_sonnei_triple_mutant(self):
        row = mt.decide("SRR8117834", results_for("SRR8117834", self.tmp))
        self.assertEqual(row["mykrobe_scheme"], "sonnei")
        self.assertEqual(row["mykrobe_species_call"], "S. sonnei")
        self.assertEqual(row["genotype"], "3.6.1.1.2")          # 'lineage' prefix removed
        self.assertEqual(row["genotype_name"], "CipR.MSM5")
        self.assertEqual(row["genotype_confidence"], "strong")
        self.assertEqual(row["qrdr_mutations"], "gyrA_D87G;gyrA_S83L;parC_S80I")
        self.assertEqual(row["num_qrdr"], "3")
        self.assertEqual(row["mykrobe_panel_version"], "20210201")
        self.assertEqual(row["warnings"], "")

    def test_flexneri_ignores_failed_sonnei_genotype(self):
        row = mt.decide("SRR4192076", results_for("SRR4192076", self.tmp))
        self.assertEqual((row["mykrobe_scheme"], row["genotype"]), ("flexneri", "3.2.1.5.5.1"))
        self.assertEqual(row["genotype_name"], "-")
        self.assertEqual(row["mykrobe_panel_version"], "20250902")

    def test_e_coli_near_miss_warns(self):
        row = mt.decide("SRR4787878", results_for("SRR4787878", self.tmp))
        self.assertEqual(row["mykrobe_scheme"], "none matched")
        self.assertEqual(row["mykrobe_species_call"], "Unknown E. coli/Shigella")
        self.assertEqual(row["genotype"], "-")
        self.assertEqual(row["qrdr_mutations"], "-")
        self.assertIn("Not S. sonnei/S. flexneri", row["warnings"])
        self.assertIn("89.474 just below the sonnei threshold", row["warnings"])
        self.assertIn("85.048 just below the flexneri threshold", row["warnings"])

    def test_not_e_coli(self):
        row = mt.decide("SRR5306599", results_for("SRR5306599", self.tmp))
        self.assertEqual(row["mykrobe_species_call"], "Not E. coli/Shigella")

    def test_manual_scheme_on_wrong_species(self):
        row = mt.decide("SRR8117834", results_for("SRR8117834", self.tmp, ("flexneri",)))
        self.assertEqual(row["mykrobe_scheme"], "none matched")
        self.assertEqual(row["qrdr_mutations"], "-")   # QRDR from a failed scheme is dropped

    def test_both_matched(self):
        res = results_for("SRR8117834", self.tmp)
        res["flexneri"]["msh"] = dict(res["flexneri"]["msh"], species="S. flexneri")
        row = mt.decide("x", res)
        self.assertEqual(row["mykrobe_scheme"], "both matched")
        self.assertEqual(row["genotype"], "-")
        self.assertIn("matched both schemes", row["warnings"])

    def test_weak_confidence_and_additional_markers(self):
        res = results_for("SRR8117834", self.tmp)
        res["sonnei"]["msh"] = dict(res["sonnei"]["msh"], confidence="weak",
                                    **{"additional markers": "lineage2 (1; 5/40)"})
        w = mt.decide("x", res)["warnings"]
        self.assertIn("weak genotype confidence", w)
        self.assertIn("additional markers present", w)

    def test_mykrobe_failure_is_reported(self):
        res = results_for("SRR8117834", self.tmp, ("sonnei",))
        res["flexneri"] = {"json": None, "msh": None, "error": "boom"}
        row = mt.decide("x", res)
        self.assertEqual(row["mykrobe_scheme"], "sonnei")
        self.assertIn("Mykrobe failed (flexneri): boom", row["warnings"])

    def test_borderline_just_above(self):
        res = results_for("SRR4192076", self.tmp, ("flexneri",))
        res["flexneri"]["msh"] = dict(res["flexneri"]["msh"], species_coverage="85.9")
        self.assertIn("85.9 just above the flexneri threshold", mt.decide("x", res)["warnings"])


class TestNames(unittest.TestCase):
    def test_sample_name_from_reads(self):
        self.assertEqual(mt.sample_name_from_reads("/a/SRR1_1.fastq.gz"), "SRR1")
        self.assertEqual(mt.sample_name_from_reads("S1_R1_001.fastq.gz"), "S1")
        self.assertEqual(mt.sample_name_from_reads("S1.fq"), "S1")

    def test_finds_bundled_panels(self):
        self.assertTrue(os.path.isfile(os.path.join(mt.find_panels(), "flexneri", "manifest.json")))


@unittest.skipUnless(HAVE_MYKROBE, "mykrobe not on PATH")
class TestEndToEnd(unittest.TestCase):
    def test_random_reads_give_one_row(self):
        tmp = tempfile.mkdtemp()
        try:
            rng = random.Random(3)
            fq = os.path.join(tmp, "rand_1.fastq")
            with open(fq, "w") as fh:
                for i in range(2000):
                    seq = "".join(rng.choice("ACGT") for _ in range(100))
                    fh.write(f"@r{i}\n{seq}\n+\n{'I' * 100}\n")
            out = os.path.join(tmp, "out")
            res = subprocess.run(
                [sys.executable, "-m", "shigella_typing.cli", "mykrobe", "--reads", fq,
                 "--sample", "random reads", "--outdir", out],
                capture_output=True, text=True, env=dict(os.environ, PYTHONPATH=TOOL))
            self.assertEqual(res.returncode, 0, res.stderr)
            with open(os.path.join(out, "mykrobe_report.tsv")) as fh:
                rows = list(csv.DictReader(fh, delimiter="\t"))
            self.assertEqual(len(rows), 1)
            self.assertEqual(list(rows[0]), mt.REPORT_COLUMNS)
            self.assertEqual(rows[0]["sample"], "random reads")
            self.assertEqual(rows[0]["mykrobe_scheme"], "none matched")
            self.assertEqual(rows[0]["mykrobe_species_call"], "Not E. coli/Shigella")
        finally:
            shutil.rmtree(tmp)


if __name__ == "__main__":
    unittest.main()
