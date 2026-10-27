"""
Unit tests for the shigella-typing command line.

Run: python -m unittest discover -s tests -v
"""
import os
import subprocess
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TOOL = os.path.join(ROOT, "tool")
sys.path.insert(0, TOOL)

from shigella_typing import __version__  # noqa: E402
from shigella_typing import cli  # noqa: E402


def run_cli(*args):
    env = dict(os.environ, PYTHONPATH=TOOL)
    return subprocess.run([sys.executable, "-m", "shigella_typing.cli", *args],
                          capture_output=True, text=True, env=env)


class TestCli(unittest.TestCase):
    def test_version(self):
        res = run_cli("--version")
        self.assertEqual(res.returncode, 0)
        self.assertIn(__version__, res.stdout)

    def test_no_command_prints_help(self):
        res = run_cli()
        self.assertEqual(res.returncode, 1)
        for name in cli.SUBCOMMANDS:
            self.assertIn(name, res.stdout)

    def test_subcommands_exist(self):
        self.assertEqual(set(cli.SUBCOMMANDS), {"shigapass", "mykrobe", "combine", "run"})


if __name__ == "__main__":
    unittest.main()
