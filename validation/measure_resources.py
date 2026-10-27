"""
Measure one command: wall time, CPU time (user + sys) and peak memory of
the largest child process. Works on macOS and Linux.

Usage: python measure_resources.py LABEL OUT.tsv -- COMMAND [ARGS ...]
Appends: label, wall_s, cpu_s, peak_rss_mb, exit_code to OUT.tsv.
"""
import os
import resource
import subprocess
import sys
import time


def main():
    label, out = sys.argv[1:3]
    cmd = sys.argv[sys.argv.index("--") + 1:]
    start = time.time()
    code = subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL).returncode
    wall = time.time() - start
    ru = resource.getrusage(resource.RUSAGE_CHILDREN)
    rss_mb = ru.ru_maxrss / (1024 * 1024 if sys.platform == "darwin" else 1024)
    new = not os.path.exists(out)
    with open(out, "a") as fh:
        if new:
            fh.write("label\twall_s\tcpu_s\tpeak_rss_mb\texit_code\n")
        fh.write(f"{label}\t{wall:.1f}\t{ru.ru_utime + ru.ru_stime:.1f}\t{rss_mb:.0f}\t{code}\n")


if __name__ == "__main__":
    main()
