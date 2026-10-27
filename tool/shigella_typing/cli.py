#!/usr/bin/env python3
"""
shigella-typing - command-line entry point.

Subcommands (each one is also a Galaxy tool; the wrappers call these):

    shigapass   ShigaPass typing of assemblies (tool 1)
    mykrobe     Mykrobe Shigella genotyping of reads (tool 2)
    combine     combine the two reports with cross-check warnings (tool 3)
    run         all three steps from one samplesheet

Standard library only; ShigaPass, Mykrobe and BLAST+ are called as programs.
"""

import argparse
import sys

from shigella_typing import __version__

SUBCOMMANDS = {
    "shigapass": "ShigaPass typing of assemblies",
    "mykrobe": "Mykrobe Shigella genotyping of reads",
    "combine": "combine ShigaPass and Mykrobe reports with cross-check warnings",
    "run": "run all three steps from a samplesheet",
}


def build_parser():
    parser = argparse.ArgumentParser(
        prog="shigella-typing",
        description="Shigella typing: ShigaPass (assemblies), Mykrobe (reads), combined report.",
    )
    parser.add_argument("--version", action="version",
                        version=f"shigella-typing {__version__}")
    sub = parser.add_subparsers(dest="command", metavar="COMMAND")
    for name, text in SUBCOMMANDS.items():
        sub.add_parser(name, help=text, description=text)
    return parser


def main(argv=None):
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.command is None:
        parser.print_help()
        return 1
    sys.stderr.write(f"shigella-typing {args.command}: not implemented yet\n")
    return 2


if __name__ == "__main__":
    sys.exit(main())
