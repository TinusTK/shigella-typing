"""
End-to-end tests on the public test data in tool/test-data (cut-down
assemblies and reads, see tool/test-data/README.md): each tool on its own,
the three tools chained, tool 1's toggle and `run`. They need ShigaPass,
BLAST+ and Mykrobe on PATH (the conda environment) and are skipped
otherwise.

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
DATA = os.path.join(TOOL, "test-data")
sys.path.insert(0, TOOL)

from shigella_typing import combine  # noqa: E402

HAVE_TOOLS = all(shutil.which(p) for p in ("ShigaPass.sh", "blastn", "mykrobe"))

TRIPLE = "QRDR triple mutant: resistance likely"
# sample: (predicted_serotype, mykrobe_scheme, genotype, qrdr_mutations, cipro_prediction)
EXPECTED = {
    "ERR5976293": ("SS", "sonnei", "3.7.25", "none", "no QRDR mutations"),
    "ERR5952732": ("SF1-5", "flexneri", "1.2.2.5.3", "none", "no QRDR mutations"),
    "ERR5888634": ("SB2", "none matched", "-", "-", "-"),
    "SRR8117834": ("-", "sonnei", "3.6.1.1.2", "gyrA_D87G;gyrA_S83L;parC_S80I", TRIPLE),
    "ERR047239": ("-", "flexneri", "2.1.2.7", "gyrA_S83L",
                  "QRDR mutation(s): reduced susceptibility likely"),
}


def data(name):
    return os.path.join(DATA, name)


def reads(sample):
    return [data(f"{sample}_1.fastq.gz"), data(f"{sample}_2.fastq.gz")]


def cli(*args):
    res = subprocess.run([sys.executable, "-m", "shigella_typing.cli", *args],
                         capture_output=True, text=True, env=dict(os.environ, PYTHONPATH=TOOL))
    if res.returncode != 0:
        raise AssertionError(f"shigella-typing {args[0]} failed:\n{res.stderr}")
    return res


def table(path):
    with open(path) as fh:
        return {r["sample"]: r for r in csv.DictReader(fh, delimiter="\t")}


@unittest.skipUnless(HAVE_TOOLS, "ShigaPass.sh / blastn / mykrobe not on PATH")
class TestEndToEnd(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.mkdtemp()
        cls.sheet = os.path.join(cls.tmp, "samples.tsv")
        with open(cls.sheet, "w") as fh:
            fh.write("sample\tassembly\tr1\tr2\n")
            for s in ("ERR5976293", "ERR5952732"):
                fh.write(f"{s}\t{data(s + '.fasta.gz')}\t" + "\t".join(reads(s)) + "\n")
            fh.write(f"ERR5888634\t{data('ERR5888634.fasta.gz')}\t\t\n")
            for s in ("SRR8117834", "SRR5306599"):
                fh.write(f"{s}\t\t" + "\t".join(reads(s)) + "\n")
        cls.run_out = os.path.join(cls.tmp, "run")
        cli("run", "--samplesheet", cls.sheet, "--outdir", cls.run_out, "--threads", "2")

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp)

    def test_shigapass(self):
        out = os.path.join(self.tmp, "sp")
        cli("shigapass", "--assembly", data("ERR5976293.fasta.gz"), data("ERR5952732.fasta.gz"),
            data("ERR5888634.fasta.gz"), data("ERR5982186.fasta.gz"), "--outdir", out)
        rows = table(os.path.join(out, "shigapass_report.tsv"))
        self.assertEqual({s: r["predicted_serotype"] for s, r in rows.items()},
                         {"ERR5976293": "SS", "ERR5952732": "SF1-5",
                          "ERR5888634": "SB2", "ERR5982186": "SD2"})
        self.assertEqual(rows["ERR5952732"]["serotype_shigapass"], "S. flexneri 1b")
        self.assertEqual(rows["ERR5976293"]["mlst_st"], "ST152")

    def test_mykrobe_paired(self):
        for sample in ("SRR8117834", "ERR047239"):
            out = os.path.join(self.tmp, "my_" + sample)
            cli("mykrobe", "--reads", *reads(sample), "--sample", sample, "--outdir", out)
            row = table(os.path.join(out, "mykrobe_report.tsv"))[sample]
            _, scheme, genotype, qrdr, cipro = EXPECTED[sample]
            self.assertEqual((row["mykrobe_scheme"], row["genotype"], row["qrdr_mutations"],
                              row["cipro_prediction"]), (scheme, genotype, qrdr, cipro))
            self.assertEqual(row["genotype_confidence"], "strong")

    def test_mykrobe_single_end_and_manual_scheme(self):
        out = os.path.join(self.tmp, "my_se")
        cli("mykrobe", "--reads", reads("SRR8117834")[0], "--outdir", out, "--scheme", "sonnei")
        row = table(os.path.join(out, "mykrobe_report.tsv"))["SRR8117834"]
        self.assertEqual((row["mykrobe_scheme"], row["genotype"]), ("sonnei", "3.6.1.1.2"))

    def test_mykrobe_borderline_e_coli(self):
        out = os.path.join(self.tmp, "my_ecoli")
        cli("mykrobe", "--reads", *reads("SRR4787878"), "--outdir", out)
        row = table(os.path.join(out, "mykrobe_report.tsv"))["SRR4787878"]
        self.assertEqual((row["mykrobe_scheme"], row["mykrobe_species_call"]),
                         ("none matched", "Unknown E. coli/Shigella"))
        self.assertIn("species coverage 89.474 just below the sonnei threshold (90)", row["warnings"])
        self.assertIn("species coverage 85.048 just below the flexneri threshold (85.5)",
                      row["warnings"])

    def test_run(self):
        rows = table(os.path.join(self.run_out, "shigella_typing_report.tsv"))
        self.assertEqual(list(next(iter(rows.values()))), combine.REPORT_COLUMNS)
        self.assertEqual(list(rows), ["ERR5976293", "ERR5952732", "ERR5888634",
                                      "SRR8117834", "SRR5306599"])
        for sample in ("ERR5976293", "ERR5952732"):
            serotype, scheme, genotype, qrdr, _ = EXPECTED[sample]
            r = rows[sample]
            self.assertEqual((r["predicted_serotype"], r["mykrobe_scheme"], r["genotype"],
                              r["qrdr_mutations"], r["warnings"]),
                             (serotype, scheme, genotype, qrdr, ""))
        self.assertEqual(rows["ERR5888634"]["warnings"], "Mykrobe not run: missing reads")
        self.assertEqual(rows["SRR8117834"]["warnings"], "ShigaPass not run: missing assembly")
        self.assertEqual(rows["SRR8117834"]["genotype"], "3.6.1.1.2")
        self.assertEqual(rows["SRR5306599"]["mykrobe_species_call"], "Not E. coli/Shigella")
        for name in ("shigapass_report.tsv", "mykrobe_report.tsv"):
            self.assertTrue(os.path.isfile(os.path.join(self.run_out, name)))

    def test_three_tools_chained_match_run(self):
        """Tools 1, 2 and 3 run separately give the same rows as `run` for
        samples that have both inputs."""
        out = os.path.join(self.tmp, "chain")
        cli("shigapass", "--assembly", data("ERR5976293.fasta.gz"), data("ERR5952732.fasta.gz"),
            "--outdir", out)
        mykrobe = []
        for sample in ("ERR5976293", "ERR5952732"):
            sub = os.path.join(out, sample)
            cli("mykrobe", "--reads", *reads(sample), "--outdir", sub)
            mykrobe.append(os.path.join(sub, "mykrobe_report.tsv"))
        cli("combine", "--shigapass", os.path.join(out, "shigapass_report.tsv"),
            "--mykrobe", *mykrobe, "--outdir", out)
        chained = table(os.path.join(out, "shigella_typing_report.tsv"))
        ran = table(os.path.join(self.run_out, "shigella_typing_report.tsv"))
        for sample in ("ERR5976293", "ERR5952732"):
            self.assertEqual(chained[sample], ran[sample])

    def test_toggle_matches_run(self):
        out = os.path.join(self.tmp, "toggle")
        sheet = os.path.join(self.tmp, "reads.tsv")
        with open(sheet, "w") as fh:
            fh.write("sample\tr1\tr2\n")
            fh.write("ERR5952732\t" + "\t".join(reads("ERR5952732")) + "\n")
        cli("shigapass", "--assembly", data("ERR5952732.fasta.gz"), "--outdir", out,
            "--with-mykrobe", "--reads-samplesheet", sheet)
        toggled = table(os.path.join(out, "shigella_typing_report.tsv"))
        ran = table(os.path.join(self.run_out, "shigella_typing_report.tsv"))
        self.assertEqual(toggled["ERR5952732"], ran["ERR5952732"])


if __name__ == "__main__":
    unittest.main()
