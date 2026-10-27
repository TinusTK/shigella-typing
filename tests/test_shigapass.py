"""
Unit tests for tool 1 (ShigaPass typing).

The parsing, naming and warning logic is tested without ShigaPass. The
end-to-end tests run only when ShigaPass.sh is on PATH (conda env from
environment.yml); real-genome results are checked by
validation/check_shigapass_examples.sh.

Run: python -m unittest discover -s tests -v
"""
import csv
import gzip
import os
import random
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TOOL = os.path.join(ROOT, "tool")
sys.path.insert(0, TOOL)

from shigella_typing import shigapass_tool as sp  # noqa: E402
from shigella_typing.utils import sample_name_from_path  # noqa: E402

HAVE_SHIGAPASS = shutil.which("ShigaPass.sh") is not None and shutil.which("blastn") is not None


class TestSpeciesSerotype(unittest.TestCase):
    def test_mapping(self):
        cases = {
            ("SS", "-"): ("S. sonnei", "-"),
            ("SF1-5", "1b"): ("S. flexneri", "S. flexneri 1b"),
            ("SF1-5", "3b atypical (oac1b)"): ("S. flexneri", "S. flexneri 3b atypical (oac1b)"),
            ("SF1-5", "Unknown"): ("S. flexneri", "S. flexneri 1-5 (subserotype unknown)"),
            ("SF6", "-"): ("S. flexneri", "S. flexneri 6"),
            ("SB2", "-"): ("S. boydii", "S. boydii 2"),
            ("SB22", "-"): ("S. boydii", "S. boydii 22"),
            ("SD1", "-"): ("S. dysenteriae", "S. dysenteriae 1"),
            ("SD3/SD16", "-"): ("S. dysenteriae", "S. dysenteriae 3/16"),
            ("SDprovBEDP02-5104", "-"): ("S. dysenteriae", "S. dysenteriae provisional BEDP02-5104"),
            ("EIEC", "-"): ("EIEC", "-"),
            ("Shigella spp.", "-"): ("Shigella spp.", "-"),
            ("Not Shigella/EIEC", "-"): ("Not Shigella/EIEC", "-"),
        }
        for (pred, flex), want in cases.items():
            self.assertEqual(sp.species_serotype(pred, flex), want, pred)

    def test_every_profile_code_is_known(self):
        """Every serotype in ShigaPass's profile table maps to a species."""
        db = os.environ.get("SP_DB_PATH")
        if not db and HAVE_SHIGAPASS:
            try:
                db = sp.find_database(sp.find_shigapass())
            except SystemExit:
                db = None
        table = os.path.join(db or "", "ShigaPass_meta_profiles_v5.csv")
        if not os.path.isfile(table):
            self.skipTest("ShigaPass databases not installed")
        with open(table) as fh:
            codes = {row["Predicted_Serotype"] for row in csv.DictReader(fh, delimiter=";")}
        for code in codes:
            self.assertTrue(sp.is_known_call(code), code)
            self.assertTrue(sp.species_serotype(code, "-")[0].startswith("S. "), code)


class TestParsing(unittest.TestCase):
    def test_summary_line(self):
        name, f = sp.parse_summary_line(
            "s0001;B1-5;139,(93.3%);ST245;ShH2(ShH2cplx);A-var3,x,16;ipaH+;SF1-5;1b;")
        self.assertEqual(name, "s0001")
        self.assertEqual((f["rfb"], f["rfb_hits"], f["rfb_pct"]), ("B1-5", "139", "93.3%"))
        self.assertEqual((f["mlst_st"], f["crispr"], f["predicted_flexserotype"]),
                         ("ST245", "A-var3,x,16", "1b"))
        self.assertEqual(f["comments"], "")

    def test_ipah_negative_line(self):
        _, f = sp.parse_summary_line("s0002;ND;ND,(0.0%);ND;ND;ND;ipaH-;Not Shigella/EIEC;;")
        self.assertEqual((f["rfb_hits"], f["rfb_pct"]), ("ND", "ND"))
        self.assertEqual(f["predicted_flexserotype"], "-")
        self.assertEqual(sp.warnings_for(f), ["ipaH negative; not serotyped"])

    def test_comments_keep_semicolons(self):
        _, f = sp.parse_summary_line(
            "s0003;C1;10,(5.0%);ST1;none;none;ipaH+;SB1;;More than one rfb is detected: C1;C2")
        self.assertEqual(f["comments"], "More than one rfb is detected: C1;C2")
        self.assertIn("multiple rfb detected", sp.warnings_for(f))


class TestWarnings(unittest.TestCase):
    def fields(self, **kw):
        f = {"rfb": "D", "rfb_hits": "1", "rfb_pct": "1%", "mlst_st": "ST1", "fliC": "x",
             "crispr": "x", "ipaH": "ipaH+", "predicted_serotype": "SS",
             "predicted_flexserotype": "-", "comments": ""}
        f.update(kw)
        return f

    def test_clean_call_has_no_warning(self):
        self.assertEqual(sp.warnings_for(self.fields()), [])

    def test_sf6(self):
        self.assertIn("S. flexneri 6 - no Flex-It genotype expected",
                      sp.warnings_for(self.fields(predicted_serotype="SF6")))

    def test_eiec_and_no_mlst(self):
        w = sp.warnings_for(self.fields(predicted_serotype="EIEC", mlst_st="none"))
        self.assertIn("no MLST profile", w)
        self.assertTrue(any("EIEC" in x for x in w))

    def test_unknown_code(self):
        w = sp.warnings_for(self.fields(predicted_serotype="SX9"))
        self.assertIn("unrecognised ShigaPass call 'SX9'", w)


class TestInputs(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def path(self, name, text=None, gz=False):
        p = os.path.join(self.tmp, name)
        opener = gzip.open if gz else open
        with opener(p, "wt") as fh:
            fh.write(text or "")
        return p

    def test_fasta_checks(self):
        out = os.path.join(self.tmp, "out.fasta")
        self.assertIsNone(sp.copy_fasta(self.path("a.fasta", ">c1\nACGT\n"), out))
        self.assertIsNone(sp.copy_fasta(self.path("b.fasta.gz", ">c1\nACGT", gz=True), out))
        with open(out) as fh:
            self.assertEqual(fh.read(), ">c1\nACGT\n")
        self.assertEqual(sp.copy_fasta(self.path("c.fasta", ""), out), "input is empty")
        self.assertEqual(sp.copy_fasta(self.path("d.txt", "hello\n"), out), "input is not FASTA")
        self.assertEqual(sp.copy_fasta(self.path("e.fasta", ">only\n"), out), "input has no sequence")

    def test_sample_names(self):
        self.assertEqual(sample_name_from_path("/x/ERR1.fasta"), "ERR1")
        self.assertEqual(sample_name_from_path("ERR1.contigs.fa.gz"), "ERR1.contigs")
        self.assertEqual(sample_name_from_path("S1.v2.fna"), "S1.v2")


@unittest.skipUnless(HAVE_SHIGAPASS, "ShigaPass.sh / BLAST+ not on PATH")
class TestEndToEnd(unittest.TestCase):
    """Runs the real ShigaPass on inputs with no Shigella content."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def test_one_row_per_input(self):
        rng = random.Random(1)
        rand = os.path.join(self.tmp, "random.fasta")
        with open(rand, "w") as fh:
            fh.write(">c1\n" + "".join(rng.choice("ACGT") for _ in range(20000)) + "\n")
        junk = os.path.join(self.tmp, "junk.txt")
        with open(junk, "w") as fh:
            fh.write("not fasta\n")
        out = os.path.join(self.tmp, "out")
        res = subprocess.run(
            [sys.executable, "-m", "shigella_typing.cli", "shigapass",
             "--assembly", rand, junk, "--name", "rand.v1 sample", "junk",
             "--outdir", out, "--raw-outputs", "summary"],
            capture_output=True, text=True, env=dict(os.environ, PYTHONPATH=TOOL))
        self.assertEqual(res.returncode, 0, res.stderr)
        with open(os.path.join(out, "shigapass_report.tsv")) as fh:
            rows = list(csv.DictReader(fh, delimiter="\t"))
        self.assertEqual([r["sample"] for r in rows], ["rand.v1 sample", "junk"])
        self.assertEqual(list(rows[0].keys()), sp.REPORT_COLUMNS)
        self.assertEqual(rows[0]["predicted_serotype"], "Not Shigella/EIEC")
        self.assertEqual(rows[0]["warnings"], "ipaH negative; not serotyped")
        self.assertEqual(rows[1]["warnings"], "ShigaPass not run: input is not FASTA")
        with open(os.path.join(out, "ShigaPass_summary.csv")) as fh:
            lines = fh.read().splitlines()
        self.assertEqual(lines[0], sp.SUMMARY_HEADER)
        self.assertTrue(lines[1].startswith("rand.v1 sample;ND;"))

    def test_duplicate_names_fail(self):
        fa = os.path.join(self.tmp, "a.fasta")
        with open(fa, "w") as fh:
            fh.write(">c\nACGT\n")
        res = subprocess.run(
            [sys.executable, "-m", "shigella_typing.cli", "shigapass",
             "--assembly", fa, fa, "--name", "x", "x", "--outdir", self.tmp],
            capture_output=True, text=True, env=dict(os.environ, PYTHONPATH=TOOL))
        self.assertNotEqual(res.returncode, 0)
        self.assertIn("duplicate sample names: x", res.stderr)


if __name__ == "__main__":
    unittest.main()
