"""Fill in missing EAD records via individual GetRecord calls.

Reads data/cjh-oai/index.tsv (the DC index) for the universe of identifiers,
then for each (repo, resource) where data/cjh-oai/records/oai_ead/repo-N/
resource-M.xml is missing, fetches the EAD record via OAI-PMH GetRecord and
saves it. Idempotent: re-running picks up where it left off because the
"file exists" check is the checkpoint.

Why this exists: ListRecords pagination on the CJH server is fragile (5-min
cursor TTL, opaque 500 errors on expired tokens). One GetRecord per missing
record is slower per-network-round-trip but robust — a failure on one record
costs us one record, not the whole rest of the harvest.
"""
from __future__ import annotations

import argparse
import csv
import re
import sys
import time
from pathlib import Path

import requests
from lxml import etree as LET

ENDPOINT = "https://archives.cjh.org/oai"
USER_AGENT = "Mozilla/5.0 (compatible; JeckeArchive-OAI/0.1; +contact: edit-me@example.com)"
EAD_NS = "urn:isbn:1-931666-22-9"
OAI_NS = "http://www.openarchives.org/OAI/2.0/"


def fetch(session, identifier: str, retries: int = 4, timeout: int = 120):
    params = {"verb": "GetRecord", "metadataPrefix": "oai_ead",
              "identifier": identifier}
    for attempt in range(retries):
        try:
            r = session.get(ENDPOINT, params=params, timeout=timeout)
            r.raise_for_status()
            return r.content
        except requests.RequestException as e:
            if attempt == retries - 1:
                raise
            time.sleep(2 ** attempt)


def extract_ead_payload(body: bytes) -> bytes | None:
    """Return the bytes of just the <ead> element (or None if not present)."""
    parser = LET.XMLParser(recover=True, huge_tree=True)
    root = LET.fromstring(body, parser=parser)
    if root is None:
        return None
    err = root.find("{%s}error" % OAI_NS)
    if err is not None:
        return None
    ead = root.find(".//{%s}ead" % EAD_NS)
    if ead is None:
        return None
    return LET.tostring(ead, xml_declaration=True, encoding="utf-8")


def main():
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    base = Path(__file__).parent.parent / "data" / "cjh-oai"
    p.add_argument("--index", default=str(base / "index.tsv"))
    p.add_argument("--out", default=str(base / "records" / "oai_ead"))
    p.add_argument("--delay", type=float, default=0.5,
                   help="seconds between requests")
    p.add_argument("--max", type=int, default=0,
                   help="stop after N new fetches (0 = unlimited)")
    args = p.parse_args()

    out_root = Path(args.out)
    out_root.mkdir(parents=True, exist_ok=True)

    # Build the canonical list of (repo, resource) tuples from the DC index.
    universe = set()
    with open(args.index, encoding="utf-8") as f:
        for r in csv.DictReader(f, delimiter="\t"):
            if r["prefix"] != "oai_dc":
                continue
            if not r.get("repo_id") or not r.get("identifier"):
                continue
            m = re.search(r"resources/(\d+)$", r["identifier"])
            if not m:
                continue
            universe.add((r["repo_id"], m.group(1)))
    print(f"DC universe: {len(universe)} records")

    have = set()
    for repo_dir in out_root.glob("repo-*"):
        repo_id = repo_dir.name.split("-", 1)[1]
        for f in repo_dir.glob("resource-*.xml"):
            res_id = f.stem.split("-", 1)[1]
            have.add((repo_id, res_id))
    print(f"already on disk: {len(have)}")

    missing = sorted(universe - have, key=lambda x: (int(x[0]), int(x[1])))
    print(f"to fetch: {len(missing)}")

    session = requests.Session()
    session.headers["User-Agent"] = USER_AGENT

    fetched = 0
    failed = []
    for i, (repo_id, res_id) in enumerate(missing, 1):
        if args.max and fetched >= args.max:
            break
        ident = f"oai:archivesspace:/repositories/{repo_id}/resources/{res_id}"
        try:
            body = fetch(session, ident)
        except Exception as e:
            failed.append((repo_id, res_id, str(e)[:120]))
            if i % 50 == 0:
                print(f"  [{i}/{len(missing)}] (fetched {fetched}, failed {len(failed)})")
            continue

        payload = extract_ead_payload(body)
        if payload is None:
            failed.append((repo_id, res_id, "no_ead_element"))
            continue

        target_dir = out_root / f"repo-{repo_id}"
        target_dir.mkdir(exist_ok=True)
        (target_dir / f"resource-{res_id}.xml").write_bytes(payload)
        fetched += 1
        if i % 50 == 0:
            print(f"  [{i}/{len(missing)}] fetched {fetched}, failed {len(failed)}")
        time.sleep(args.delay)

    print(f"done. fetched={fetched}, failed={len(failed)}, "
          f"remaining_missing={len(missing) - i if missing else 0}")
    if failed:
        log = Path(args.out).parent / "fill_ead_failures.tsv"
        with log.open("w", encoding="utf-8") as f:
            f.write("repo_id\tresource_id\terror\n")
            for repo_id, res_id, err in failed:
                f.write(f"{repo_id}\t{res_id}\t{err}\n")
        print(f"failures logged to {log}")


if __name__ == "__main__":
    main()
