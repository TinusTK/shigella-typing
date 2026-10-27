#!/usr/bin/env python3
"""Upstream update check (Phase 9), run by .github/workflows/update_check.yml.

Compares upstream against upstream_versions.yml:
  - Mykrobe, ShigaPass: latest bioconda version (pinned, updated on change)
  - BLAST: latest bioconda version (reported only)
  - ShigaPass upstream main commit (reported only: we install from bioconda)
  - mykrobeshig upstream main commit (vendored, re-copied on change)
  - Mykrobe panels sonnei / flexneri from Mykrobe's panel manifest

Subcommands:
  check   --changes FILE --summary FILE   what changed (JSON) and a summary
  apply   --changes FILE --notes FILE     update pins, re-vendor, bump patch
                                          version, CHANGELOG entry
  panels  --changes FILE                  re-populate panels/ with mykrobe
  report  --outdir DIR                    `shigella-typing run` on test data
  compare BEFORE.tsv AFTER.tsv            calls that changed (markdown)

Never merges, tags or publishes: the workflow opens a pull request.
Standard library only.
"""
import argparse
import csv
import datetime
import hashlib
import json
import os
import re
import subprocess
import sys
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PINS = "upstream_versions.yml"
MANIFEST = ("https://raw.githubusercontent.com/Mykrobe-tools/mykrobe-data/"
            "main/mykrobe_panels_manifest.json")
# Vendored mykrobeshig files: upstream path -> path under the package
VENDORED = {
    "mykrobeshig/__init__.py": "__init__.py",
    "mykrobeshig/parser.py": "parser.py",
    "mykrobeshig/data/__init__.py": "data/__init__.py",
    "mykrobeshig/data/alleles_sonnei.txt": "data/alleles_sonnei.txt",
    "LICENSE": "LICENSE",
}
VENDOR_DIR = "tool/shigella_typing/mykrobeshig"
# Combined-report columns compared before and after an update
CALLS = ("species_shigapass", "serotype_shigapass", "mykrobe_scheme",
         "mykrobe_species_call", "genotype", "genotype_name",
         "genotype_confidence", "qrdr_mutations", "cipro_prediction", "warnings")


# --- small helpers -----------------------------------------------------------

def path(rel):
    return os.path.join(ROOT, rel)


def read(rel):
    with open(path(rel)) as fh:
        return fh.read()


def write(rel, text):
    with open(path(rel), "w") as fh:
        fh.write(text)


def fetch(url, raw=False):
    req = urllib.request.Request(url, headers={"User-Agent": "shigella-typing-update-check"})
    token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    if token and url.startswith("https://api.github.com/"):
        req.add_header("Authorization", f"Bearer {token}")
    with urllib.request.urlopen(req, timeout=120) as resp:
        data = resp.read()
    return data if raw else data.decode()


def bioconda_latest(package):
    return json.loads(fetch(f"https://api.anaconda.org/package/bioconda/{package}"))["latest_version"]


def github_main(repo):
    d = json.loads(fetch(f"https://api.github.com/repos/{repo}/commits/main"))
    return d["sha"], d["commit"]["committer"]["date"][:10]


def yml_get(text, keys):
    """Value at a key path in the simple upstream_versions.yml layout."""
    return _yml_find(text, keys)[1]


def yml_set(text, keys, value):
    """Replace the value at a key path, keeping quotes and comments."""
    lines = text.split("\n")
    i, _ = _yml_find(text, keys)
    m = re.match(r'^(\s*[\w-]+:\s*)("?)([^"#\s]*)("?)(.*)$', lines[i])
    lines[i] = f"{m.group(1)}{m.group(2)}{value}{m.group(4)}{m.group(5)}"
    return "\n".join(lines)


def _yml_find(text, keys):
    lines, depth, indent = text.split("\n"), 0, -1
    for i, line in enumerate(lines):
        m = re.match(r'^(\s*)([\w-]+):\s*"?([^"#\s]*)"?', line)
        if not m or line.lstrip().startswith("#"):
            continue
        ind = len(m.group(1))
        if depth and ind <= indent:
            raise KeyError(".".join(keys))
        if m.group(2) == keys[depth] and ind > indent:
            if depth == len(keys) - 1:
                return i, m.group(3)
            depth, indent = depth + 1, ind
    raise KeyError(".".join(keys))


def replace(rel, old, new, count_ok=lambda n: n > 0):
    """Replace old with new in a file; returns the number of replacements."""
    text = read(rel)
    n = text.count(old)
    if not count_ok(n):
        raise SystemExit(f"{rel}: expected '{old}', found it {n} times")
    write(rel, text.replace(old, new))
    return n


def esc(version):
    return version.replace(".", "\\.")


# --- check -------------------------------------------------------------------

def check(args):
    pins = read(PINS)
    changes, rows = {}, []

    for pkg in ("mykrobe", "shigapass", "blast"):
        cur, new = yml_get(pins, [pkg, "version"]), bioconda_latest(pkg)
        info = pkg == "blast"
        rows.append((f"{pkg} (bioconda)", cur, new, "report only" if info else ""))
        if new != cur and not info:
            changes[pkg] = {"old": cur, "new": new}

    cur = yml_get(pins, ["shigapass", "upstream_main_sha"])
    new, date = github_main("imanyass/ShigaPass")
    rows.append(("ShigaPass upstream main", cur[:7], f"{new[:7]} ({date})", "report only"))

    cur = yml_get(pins, ["mykrobeshig", "sha"])
    new, date = github_main("ShigellaGenomics/mykrobeshig")
    rows.append(("mykrobeshig upstream main", cur[:7], f"{new[:7]} ({date})", ""))
    if new != cur:
        changes["mykrobeshig"] = {"old": cur, "new": new, "date": date}

    manifest = json.loads(fetch(MANIFEST))
    for species in ("sonnei", "flexneri"):
        cur = yml_get(pins, ["panels", species, "version"])
        latest = manifest[species]
        rows.append((f"Mykrobe panel {species}", cur, latest["version"], ""))
        if latest["version"] != cur:
            changes[f"panel_{species}"] = {
                "species": species, "old": cur, "new": latest["version"],
                "old_url": yml_get(pins, ["panels", species, "url"]), "url": latest["url"],
                "old_sha256": yml_get(pins, ["panels", species, "sha256"])}

    with open(args.changes, "w") as fh:
        json.dump(changes, fh, indent=2)
    lines = ["| Upstream | Pinned | Latest | |", "|---|---|---|---|"]
    lines += [f"| {a} | {b} | {c} | {'**changed**' if b != c.split(' ')[0] and not d else d} |"
              for a, b, c, d in rows]
    lines.append("")
    lines.append("Changes found: " + (", ".join(changes) if changes else "none - all up to date"))
    with open(args.summary, "w") as fh:
        fh.write("\n".join(lines) + "\n")
    print("\n".join(lines))
    out = os.environ.get("GITHUB_OUTPUT")
    if out:
        with open(out, "a") as fh:
            fh.write(f"changed={'true' if changes else 'false'}\n")


# --- apply -------------------------------------------------------------------

def bump_patch(version):
    major, minor, patch = version.split(".")
    return f"{major}.{minor}.{int(patch) + 1}"


def apply(args):
    with open(args.changes) as fh:
        changes = json.load(fh)
    if not changes:
        raise SystemExit("no changes to apply")
    pins, notes = read(PINS), []
    today = datetime.date.today().isoformat()

    for pkg, token in (("mykrobe", "MYKROBE"), ("shigapass", "SHIGAPASS")):
        if pkg not in changes:
            continue
        old, new = changes[pkg]["old"], changes[pkg]["new"]
        pins = yml_set(pins, [pkg, "version"], new)
        replace("tool/macros.xml", f'<token name="@{token}_VERSION@">{old}</token>',
                f'<token name="@{token}_VERSION@">{new}</token>', lambda n: n == 1)
        replace("environment.yml", f"- {pkg}={old}\n", f"- {pkg}={new}\n", lambda n: n == 1)
        for xml in ("tool/shigapass_typing.xml", "tool/shigella_typing_combine.xml"):
            replace(xml, esc(old), esc(new), lambda n: True)
        notes.append(f"{pkg} {old} -> {new} (bioconda)")

    if "mykrobeshig" in changes:
        c = changes["mykrobeshig"]
        for up, local in VENDORED.items():
            data = fetch(f"https://raw.githubusercontent.com/ShigellaGenomics/mykrobeshig/{c['new']}/{up}", raw=True)
            with open(path(f"{VENDOR_DIR}/{local}"), "wb") as fh:
                fh.write(data)
        pins = yml_set(pins, ["mykrobeshig", "sha"], c["new"])
        replace(f"{VENDOR_DIR}/UPSTREAM.md", f"`{c['old']}`", f"`{c['new']}`", lambda n: n == 1)
        text = read(f"{VENDOR_DIR}/UPSTREAM.md")
        write(f"{VENDOR_DIR}/UPSTREAM.md",
              re.sub(rf"(`{c['new']}`) \(\d{{4}}-\d{{2}}-\d{{2}}\)", rf"\1 ({c['date']})", text))
        notes.append(f"mykrobeshig {c['old'][:7]} -> {c['new'][:7]} "
                     f"(https://github.com/ShigellaGenomics/mykrobeshig/compare/{c['old']}...{c['new']})")

    for key in ("panel_sonnei", "panel_flexneri"):
        if key not in changes:
            continue
        c = changes[key]
        sha = hashlib.sha256(fetch(c["url"], raw=True)).hexdigest()
        c["sha256"] = sha
        pins = yml_set(pins, ["panels", c["species"], "version"], c["new"])
        pins = yml_set(pins, ["panels", c["species"], "url"], c["url"])
        pins = yml_set(pins, ["panels", c["species"], "sha256"], sha)
        for doc in ("README.md", "tool/macros.xml", "panels/README.md", "panels/SOURCES.md",
                    "tool/shigapass_typing.xml", "tool/shigella_typing_combine.xml"):
            replace(doc, c["old"], c["new"], lambda n: True)
        replace("panels/SOURCES.md", c["old_sha256"], sha, lambda n: True)
        replace("panels/SOURCES.md", c["old_url"], c["url"], lambda n: True)
        notes.append(f"Mykrobe {c['species']} panel {c['old']} -> {c['new']}")

    pins = re.sub(r"^# Checked \d{4}-\d{2}-\d{2}\.", f"# Checked {today}.", pins, flags=re.M)
    write(PINS, pins)
    with open(args.changes, "w") as fh:
        json.dump(changes, fh, indent=2)

    # Patch version bump everywhere the tool version lives
    init = "tool/shigella_typing/__init__.py"
    old = re.search(r'^__version__ = "(.+)"$', read(init), re.M).group(1)
    new = bump_patch(old)
    suffix = re.search(r'<token name="@VERSION_SUFFIX@">(\d+)</token>', read("tool/macros.xml")).group(1)
    replace(init, f'__version__ = "{old}"', f'__version__ = "{new}"', lambda n: n == 1)
    replace("tool/macros.xml", f'<token name="@TOOL_VERSION@">{old}</token>',
            f'<token name="@TOOL_VERSION@">{new}</token>', lambda n: n == 1)
    replace("tool/macros.xml", f'<token name="@VERSION_SUFFIX@">{suffix}</token>',
            '<token name="@VERSION_SUFFIX@">0</token>', lambda n: n == 1)
    for wf in ("workflows/shigella_typing_separate.gxwf.yml", "workflows/shigella_typing_toggle.gxwf.yml"):
        replace(wf, f"{old}+galaxy{suffix}", f"{new}+galaxy0")
        replace(wf, f'release: "{old}"', f'release: "{new}"', lambda n: n == 1)
    replace("CITATION.cff", f"version: {old}\n", f"version: {new}\n", lambda n: n == 1)
    write("CITATION.cff", re.sub(r"^date-released: .*$", f"date-released: {today}",
                                 read("CITATION.cff"), flags=re.M))
    entry = f"## {new} ({today})\n\nUpstream update (automatic check):\n\n" + \
        "".join(f"- {n}\n" for n in notes) + "\n"
    replace("CHANGELOG.md", "# Changelog\n\n", "# Changelog\n\n" + entry, lambda n: n == 1)

    with open(args.notes, "w") as fh:
        fh.write(f"Version {old} -> {new}\n\n" + "".join(f"- {n}\n" for n in notes))
    print(f"Applied: version {old} -> {new}; " + "; ".join(notes))


def panels(args):
    with open(args.changes) as fh:
        changes = json.load(fh)
    species = [c["species"] for k, c in changes.items() if k.startswith("panel_")]
    if not species:
        print("no panel changes")
        return
    subprocess.run(["mykrobe", "panels", "update_metadata", "--panels_dir", path("panels")], check=True)
    for s in species:
        subprocess.run(["mykrobe", "panels", "update_species", "--panels_dir", path("panels"), s], check=True)


# --- report / compare --------------------------------------------------------

def report(args):
    data = path("tool/test-data")
    files = set(os.listdir(data))
    samples = sorted({f.split(".fasta")[0] for f in files if f.endswith(".fasta.gz")} |
                     {f[:-len("_1.fastq.gz")] for f in files if f.endswith("_1.fastq.gz")})
    os.makedirs(args.outdir, exist_ok=True)
    sheet = os.path.join(args.outdir, "samples.tsv")
    with open(sheet, "w") as fh:
        fh.write("sample\tassembly\tr1\tr2\n")
        for s in samples:
            asm = os.path.join(data, f"{s}.fasta.gz") if f"{s}.fasta.gz" in files else ""
            r1, r2 = (os.path.join(data, f"{s}_{m}.fastq.gz") for m in (1, 2))
            reads = f"{r1}\t{r2}" if f"{s}_1.fastq.gz" in files else "\t"
            fh.write(f"{s}\t{asm}\t{reads}\n")
    subprocess.run(["shigella-typing", "run", "--samplesheet", sheet,
                    "--outdir", os.path.join(args.outdir, "run"), "--threads", "2"], check=True)


def compare(args):
    def table(p):
        with open(p) as fh:
            return {r["sample"]: r for r in csv.DictReader(fh, delimiter="\t")}
    before, after = table(args.before), table(args.after)
    diffs = []
    for s in sorted(set(before) | set(after)):
        b, a = before.get(s, {}), after.get(s, {})
        for col in CALLS:
            if b.get(col, "(missing)") != a.get(col, "(missing)"):
                diffs.append(f"| {s} | {col} | {b.get(col, '(missing)') or '-'} | {a.get(col, '(missing)') or '-'} |")
    if diffs:
        print("| Sample | Column | Before | After |\n|---|---|---|---|\n" + "\n".join(diffs))
    else:
        print(f"No calls changed on the {len(after)} test-data samples.")


def main():
    p = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sub = p.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("check")
    c.add_argument("--changes", required=True)
    c.add_argument("--summary", required=True)
    a = sub.add_parser("apply")
    a.add_argument("--changes", required=True)
    a.add_argument("--notes", required=True)
    pn = sub.add_parser("panels")
    pn.add_argument("--changes", required=True)
    r = sub.add_parser("report")
    r.add_argument("--outdir", required=True)
    cp = sub.add_parser("compare")
    cp.add_argument("before")
    cp.add_argument("after")
    args = p.parse_args()
    {"check": check, "apply": apply, "panels": panels, "report": report, "compare": compare}[args.cmd](args)


if __name__ == "__main__":
    sys.exit(main())
