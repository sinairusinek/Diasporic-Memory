#!/usr/bin/env python3
"""Run the annotator build pipeline end to end.

Stages 1-4 and 9 are free and deterministic. Stages 5-7 call the Claude API and
cost money; stage 8 needs BLOB_READ_WRITE_TOKEN. Run the free stages first and
inspect the output before spending anything:

    python code/annotator/build_all.py --free-only
    python code/annotator/build_all.py            # everything available

Every stage is idempotent and hash-gated, so re-running is cheap.
"""
import argparse
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent

STAGES = [
    ("select_docs",           "curate the visit manifest",           "free"),
    ("build_written",         "written bundles from page OCR",       "free"),
    ("build_oral",            "Israelkorpus excerpt windows",        "free"),
    ("prehighlight_keywords", "lexical Heimat / return signals",     "free"),
    ("prehighlight_claude",   "passages carrying each rationale",    "api"),
    ("translate_he",          "Hebrew translation, page by page",    "api"),
    ("project_highlights",    "project highlights onto the Hebrew",  "api"),
    ("build_scans",           "WebP derivatives -> Vercel Blob",     "blob"),
    ("build_index",           "assemble index.json and validate",    "free"),
]


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--free-only", action="store_true",
                    help="skip every stage that costs money")
    ap.add_argument("--from", dest="start", help="start at this stage")
    ap.add_argument("--only", nargs="*", help="run only these stages")
    ap.add_argument("--docs", nargs="*", help="pass through to each stage")
    args, passthrough = ap.parse_known_args()

    started = args.start is None
    for name, blurb, cost in STAGES:
        if args.only and name not in args.only:
            continue
        if not started:
            if name != args.start:
                continue
            started = True
        if args.free_only and cost != "free":
            print(f"— skip {name}  ({blurb}) — {cost}")
            continue

        cmd = [sys.executable, str(HERE / f"{name}.py")]
        if args.docs and name not in ("select_docs", "build_index"):
            cmd += ["--docs", *args.docs]
        cmd += passthrough
        print(f"\n=== {name} — {blurb}")
        r = subprocess.run(cmd, cwd=HERE)
        if r.returncode != 0:
            # build_index is the validation gate; a failure there means the
            # bundles are internally inconsistent and must not be shipped.
            raise SystemExit(f"{name} failed with {r.returncode}")

    print("\nNext:  cd annotator && npm run sync && npm run dev")


if __name__ == "__main__":
    main()
