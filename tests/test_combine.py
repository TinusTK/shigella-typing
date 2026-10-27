"""
Unit tests for tool 3 (Combine Shigella report) and the samplesheet reader
used by tool 1's toggle and `run`. Every cross-check warning in the plan
(section 5) has a test. No external programs needed.

Run: python -m unittest discover -s tests -v
"""
import csv
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TOOL = os.path.join(ROOT, "tool")
sys.path.insert(0, TOOL)

from shigella_typing import combine, mykrobe_tool, pipeline, shigapass_tool  # noqa: E402
from shigella_typing.utils import write_tsv  # noqa: E402

SPECIES = {"SS": ("S. sonnei", "-"), "SF1-5": ("S. flexneri", "S. flexneri 1b"),
           "SF6": ("S. flexneri", "S. flexneri 6"), "SB2": ("S. boydii", "S. boydii 2"),
           "SD1": ("S. dysenteriae", "S. dysenteriae 1"), "EIEC": ("EIEC", "-"),
           "Not Shigella/EIEC": ("Not Shigella/EIEC", "-")}
MY_SPECIES = {"sonnei": "S. sonnei", "flexneri": "S. flexneri"}


def sp_row(sample, call, warnings=""):
    row = {c: "x" for c in shigapass_tool.REPORT_COLUMNS}
    species, serotype = SPECIES[call]
    row.update(sample=sample, predicted_serotype=call, species_shigapass=species,
               serotype_shigapass=serotype, warnings=warnings, shigapass_version="1.5.0")
    return row


def my_row(sample, scheme, species_call=None, warnings=""):
    row = {c: "y" for c in mykrobe_tool.REPORT_COLUMNS}
    row.update(sample=sample, mykrobe_scheme=scheme,
               mykrobe_species_call=species_call or MY_SPECIES.get(scheme, "Unknown E. coli/Shigella"),
               warnings=warnings, mykrobe_version="0.13.0", mykrobe_panel_version="20250902")
    return row


def warnings_of(sp, my):
    return combine.combine_rows([sp] if sp else [], [my] if my else [])[0]["warnings"]


class TestCrossCheck(unittest.TestCase):
    def test_concordant(self):
        self.assertEqual(warnings_of(sp_row("a", "SS"), my_row("a", "sonnei")), "")
        self.assertEqual(warnings_of(sp_row("a", "SF1-5"), my_row("a", "flexneri")), "")

    def test_discordant_species(self):
        self.assertEqual(warnings_of(sp_row("a", "SS"), my_row("a", "flexneri")),
                         "Discordant: ShigaPass S. sonnei, Mykrobe S. flexneri - check")
        self.assertEqual(warnings_of(sp_row("a", "SF1-5"), my_row("a", "sonnei")),
                         "Discordant: ShigaPass S. flexneri 1b, Mykrobe S. sonnei - check")

    def test_shigapass_species_but_no_mykrobe_match(self):
        w = warnings_of(sp_row("a", "SS"),
                        my_row("a", "none matched", warnings="Not S. sonnei/S. flexneri"))
        self.assertEqual(w, "ShigaPass S. sonnei but Mykrobe did not match the sonnei scheme "
                            "- check reads/assembly")

    def test_not_shigella_but_mykrobe_species(self):
        w = warnings_of(sp_row("a", "Not Shigella/EIEC", "ipaH negative; not serotyped"),
                        my_row("a", "sonnei"))
        self.assertEqual(w, "ipaH negative; not serotyped; Discordant: ShigaPass "
                            "Not Shigella/EIEC, Mykrobe S. sonnei - check assembly")

    def test_no_scheme_species_is_informational(self):
        for call, species in (("SB2", "S. boydii"), ("SD1", "S. dysenteriae"),
                              ("SF6", "S. flexneri"), ("EIEC", "EIEC")):
            for myk in ("Unknown E. coli/Shigella", "Not E. coli/Shigella"):
                w = warnings_of(sp_row("a", call),
                                my_row("a", "none matched", myk, "Not S. sonnei/S. flexneri"))
                self.assertEqual(w, f"No Mykrobe genotyping scheme for {species}; serotype only")

    def test_not_shigella_both_tools(self):
        w = warnings_of(sp_row("a", "Not Shigella/EIEC"),
                        my_row("a", "none matched", "Not E. coli/Shigella", "Not S. sonnei/S. flexneri"))
        self.assertEqual(w, "Not Shigella - check organism")

    def test_not_shigella_unknown_e_coli_keeps_tool_warnings(self):
        w = warnings_of(sp_row("a", "Not Shigella/EIEC", "ipaH negative; not serotyped"),
                        my_row("a", "none matched", "Unknown E. coli/Shigella",
                               "Not S. sonnei/S. flexneri"))
        self.assertEqual(w, "ipaH negative; not serotyped; Not S. sonnei/S. flexneri")

    def test_missing_sides(self):
        rows = combine.combine_rows([sp_row("a", "SS")], [my_row("b", "flexneri", warnings="w2")])
        self.assertEqual([(r["sample"], r["warnings"]) for r in rows],
                         [("a", "Missing from Mykrobe report"),
                          ("b", "w2; Missing from ShigaPass report")])
        self.assertEqual(rows[0]["genotype"], "-")
        self.assertEqual(rows[1]["rfb"], "-")

    def test_one_side_not_run_adds_nothing(self):
        failed = shigapass_tool.failed_row("a", "input is empty")
        w = warnings_of(failed, my_row("a", "sonnei"))
        self.assertEqual(w, "ShigaPass not run: input is empty")


class TestCombine(unittest.TestCase):
    def test_columns_match_draft_report(self):
        self.assertEqual(len(combine.REPORT_COLUMNS), 30)
        self.assertEqual(combine.REPORT_COLUMNS[:3], ["sample", "rfb", "rfb_hits"])
        self.assertEqual(combine.REPORT_COLUMNS[12:14], ["serotype_shigapass", "mykrobe_scheme"])
        self.assertEqual(combine.REPORT_COLUMNS[-5:], ["warnings", "shigapass_version",
                                                       "mykrobe_version", "mykrobe_panel_version",
                                                       "tool_version"])

    def test_values_and_versions(self):
        row = combine.combine_rows([sp_row("a", "SS", "w1")], [my_row("a", "sonnei", warnings="w2")])[0]
        self.assertEqual(row["warnings"], "w1; w2")
        self.assertEqual((row["shigapass_version"], row["mykrobe_version"],
                          row["mykrobe_panel_version"]), ("1.5.0", "0.13.0", "20250902"))
        self.assertEqual(row["rfb"], "x")
        self.assertEqual(row["genotype"], "y")

    def test_duplicates_fail(self):
        with self.assertRaises(SystemExit) as cm:
            combine.combine_rows([sp_row("a", "SS"), sp_row("a", "SS")], [])
        self.assertIn("duplicate sample names in the ShigaPass report(s): a", str(cm.exception))

    def test_strip_suffixes(self):
        self.assertEqual(combine.strip_suffixes("S1_contigs.fasta"), "S1")
        self.assertEqual(combine.strip_suffixes("S1.fa"), "S1")
        rows = combine.combine_rows([sp_row("S1_contigs", "SS")], [my_row("S1", "sonnei")], strip=True)
        self.assertEqual([(r["sample"], r["warnings"]) for r in rows], [("S1", "")])
        rows = combine.combine_rows([sp_row("S1_contigs", "SS")], [my_row("S1", "sonnei")])
        self.assertEqual(len(rows), 2)  # exact match by default

    def test_cli_with_several_reports(self):
        tmp = tempfile.mkdtemp()
        try:
            sp = os.path.join(tmp, "sp.tsv")
            write_tsv(sp, shigapass_tool.REPORT_COLUMNS, [sp_row("a", "SS"), sp_row("b", "SB2")])
            my1, my2 = os.path.join(tmp, "m1.tsv"), os.path.join(tmp, "m2.tsv")
            write_tsv(my1, mykrobe_tool.REPORT_COLUMNS, [my_row("a", "sonnei")])
            write_tsv(my2, mykrobe_tool.REPORT_COLUMNS, [my_row("b", "none matched")])
            res = subprocess.run([sys.executable, "-m", "shigella_typing.cli", "combine",
                                  "--shigapass", sp, "--mykrobe", my1, my2, "--outdir", tmp],
                                 capture_output=True, text=True, env=dict(os.environ, PYTHONPATH=TOOL))
            self.assertEqual(res.returncode, 0, res.stderr)
            with open(os.path.join(tmp, "shigella_typing_report.tsv")) as fh:
                rows = list(csv.DictReader(fh, delimiter="\t"))
            self.assertEqual(list(rows[0]), combine.REPORT_COLUMNS)
            self.assertEqual([r["sample"] for r in rows], ["a", "b"])
            # wrong file type gives a clear error
            res = subprocess.run([sys.executable, "-m", "shigella_typing.cli", "combine",
                                  "--shigapass", my1, "--mykrobe", my1, "--outdir", tmp],
                                 capture_output=True, text=True, env=dict(os.environ, PYTHONPATH=TOOL))
            self.assertNotEqual(res.returncode, 0)
            self.assertIn("is not a ShigaPass report", res.stderr)
        finally:
            shutil.rmtree(tmp)


class TestSamplesheet(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def sheet(self, text):
        p = os.path.join(self.tmp, "s.tsv")
        with open(p, "w") as fh:
            fh.write(text)
        return p

    def test_paths_and_empty_fields(self):
        p = self.sheet("sample\tassembly\tr1\tr2\n"
                       "A\ta.fa\ta_1.fq\ta_2.fq\n"
                       "B\t\tb.fq\t\n"
                       "C\t/abs/c.fa\t\t\n")
        got = pipeline.read_samplesheet(p, need_assembly=True)
        self.assertEqual(got[0], ("A", os.path.join(self.tmp, "a.fa"),
                                  [os.path.join(self.tmp, "a_1.fq"), os.path.join(self.tmp, "a_2.fq")]))
        self.assertEqual(got[1], ("B", None, [os.path.join(self.tmp, "b.fq")]))
        self.assertEqual(got[2], ("C", "/abs/c.fa", []))

    def test_errors(self):
        with self.assertRaises(SystemExit):
            pipeline.read_samplesheet(self.sheet("sample\tr1\nA\tx\nA\ty\n"))
        with self.assertRaises(SystemExit):
            pipeline.read_samplesheet(self.sheet("sample\tr1\nA\tx\n"), need_assembly=True)


if __name__ == "__main__":
    unittest.main()
