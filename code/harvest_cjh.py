"""Harvest the Center for Jewish History ArchivesSpace OAI-PMH endpoint.

Endpoint: https://archives.cjh.org/oai
Set:     full_as_oai  (all five partner repositories: LBI, YIVO, AJHS, ASF, YU Museum)

Outputs (under --out, default ../data/cjh-oai):
  raw/{prefix}/page-NNNN.xml         original OAI envelopes, in order
  records/{prefix}/repo-{R}/resource-{ID}.xml   one file per harvested record
  index.tsv                          identifier, datestamp, repo_id, repo_name, title, path

Usage:
  python harvest_cjh.py                       # default: oai_ead, full set
  python harvest_cjh.py --prefix oai_dc       # lightweight Dublin Core run
  python harvest_cjh.py --from 2025-01-01     # incremental
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path
from typing import Optional
from urllib.parse import urlencode
from xml.etree import ElementTree as ET

import requests

try:
    from lxml import etree as LET  # tolerant parser for malformed EAD payloads
    _HAS_LXML = True
except ImportError:
    LET = None
    _HAS_LXML = False

ENDPOINT = "https://archives.cjh.org/oai"
# Cloudflare in front of archives.cjh.org rejects User-Agents containing the
# word "Harvester" — keep this string descriptive but neutral.
USER_AGENT = "Mozilla/5.0 (compatible; JeckeArchive-OAI/0.1; +contact: edit-me@example.com)"

NS = {
    "o": "http://www.openarchives.org/OAI/2.0/",
    "dc": "http://purl.org/dc/elements/1.1/",
    "oai_dc": "http://www.openarchives.org/OAI/2.0/oai_dc/",
    "ead": "urn:isbn:1-931666-22-9",
}


def oai_request(session, params, retries=6, backoff=2.0):
    # EAD pages are large and the server is slow per request; give it real time.
    for attempt in range(retries):
        try:
            r = session.get(ENDPOINT, params=params, timeout=180)
            r.raise_for_status()
            return r.text
        except requests.RequestException as e:
            if attempt == retries - 1:
                raise
            wait = backoff ** attempt
            print(f"  request failed ({e}); retrying in {wait:.0f}s", file=sys.stderr)
            time.sleep(wait)


def parse_identifier(ident: str):
    """oai:archivesspace:/repositories/4/resources/42 -> ('4', '42')"""
    if "/repositories/" not in ident:
        return (None, None)
    tail = ident.split("/repositories/", 1)[1]
    repo, _, rest = tail.partition("/")
    res_id = rest.rsplit("/", 1)[-1] if rest else None
    return (repo, res_id)


def extract_repo_name(metadata_el):
    """Best-effort repository name from EAD or Dublin Core record."""
    if metadata_el is None:
        return ""
    # EAD: <repository><corpname>
    corpname = metadata_el.find(".//ead:repository/ead:corpname", NS)
    if corpname is not None and corpname.text:
        return corpname.text.strip()
    # Dublin Core: <dc:publisher> or <dc:source>
    for tag in ("dc:publisher", "dc:source"):
        el = metadata_el.find(f".//{tag}", NS)
        if el is not None and el.text:
            return el.text.strip()
    return ""


def extract_title(metadata_el):
    if metadata_el is None:
        return ""
    # EAD: <unittitle> inside <did>
    title = metadata_el.find(".//ead:archdesc/ead:did/ead:unittitle", NS)
    if title is not None:
        return "".join(title.itertext()).strip()
    # DC
    dc_title = metadata_el.find(".//dc:title", NS)
    if dc_title is not None and dc_title.text:
        return dc_title.text.strip()
    return ""


def harvest(prefix: str, set_spec: str, out: Path, from_date: Optional[str],
            until_date: Optional[str], delay: float):
    raw_dir = out / "raw" / prefix
    rec_dir = out / "records" / prefix
    state_dir = out / "state"
    raw_dir.mkdir(parents=True, exist_ok=True)
    rec_dir.mkdir(parents=True, exist_ok=True)
    state_dir.mkdir(parents=True, exist_ok=True)

    index_path = out / "index.tsv"
    new_index = not index_path.exists()
    index_fh = index_path.open("a", encoding="utf-8")
    if new_index:
        index_fh.write("prefix\tidentifier\tdatestamp\trepo_id\trepo_name\ttitle\tpath\n")

    session = requests.Session()
    session.headers["User-Agent"] = USER_AGENT

    # Resume from checkpoint if it matches our parameters; otherwise start fresh.
    checkpoint_path = state_dir / f"{prefix}.checkpoint.json"
    params = {"verb": "ListRecords", "metadataPrefix": prefix, "set": set_spec}
    if from_date:
        params["from"] = from_date
    if until_date:
        params["until"] = until_date
    resume_page_offset = 0
    if checkpoint_path.exists():
        try:
            import json
            cp = json.loads(checkpoint_path.read_text())
            if (cp.get("prefix") == prefix and cp.get("set") == set_spec
                    and cp.get("from") == from_date and cp.get("until") == until_date
                    and cp.get("token")):
                params = {"verb": "ListRecords",
                          "resumptionToken": cp["token"]}
                resume_page_offset = cp.get("page", 0)
                print(f"resuming from checkpoint at page {resume_page_offset + 1}")
        except Exception as e:
            print(f"  checkpoint load failed ({e}); starting fresh", file=sys.stderr)

    page = resume_page_offset
    total = 0
    while True:
        page += 1
        print(f"page {page}: {urlencode(params)}")
        body = oai_request(session, params)
        raw_path = raw_dir / f"page-{page:04d}.xml"
        raw_path.write_text(body, encoding="utf-8")

        # Resumption token: extract from raw text via regex so a mid-page XML
        # malformation cannot cost us the rest of the harvest.
        import re as _re
        tok_match = _re.search(
            r"<resumptionToken[^>]*>([^<]*)</resumptionToken>", body)
        recovered_token = (tok_match.group(1) or "").strip() if tok_match else ""

        try:
            if _HAS_LXML:
                parser = LET.XMLParser(recover=True, huge_tree=True)
                root = LET.fromstring(body.encode("utf-8"), parser=parser)
            else:
                root = ET.fromstring(body)
        except (ET.ParseError, Exception) as e:
            print(f"  XML parse failed on page {page} ({e}); using token to continue",
                  file=sys.stderr)
            if not recovered_token:
                break
            params = {"verb": "ListRecords", "resumptionToken": recovered_token}
            time.sleep(delay)
            continue
        err = root.find("o:error", NS) if not _HAS_LXML else root.find("o:error", NS)
        if err is not None:
            print(f"OAI error: {err.get('code')} - {err.text}", file=sys.stderr)
            break

        records = root.findall(".//o:record", NS)
        page_record_count = 0
        for rec in records:
            header = rec.find("o:header", NS)
            if header is None:
                continue
            ident = (header.findtext("o:identifier", default="", namespaces=NS) or "").strip()
            datestamp = (header.findtext("o:datestamp", default="", namespaces=NS) or "").strip()
            status = header.get("status", "")
            metadata_el = rec.find("o:metadata", NS)

            repo_id, res_id = parse_identifier(ident)
            repo_name = extract_repo_name(metadata_el)
            title = extract_title(metadata_el).replace("\t", " ").replace("\n", " ")

            if status == "deleted" or metadata_el is None or repo_id is None or res_id is None:
                rel = ""
            else:
                target_dir = rec_dir / f"repo-{repo_id}"
                target_dir.mkdir(exist_ok=True)
                target = target_dir / f"resource-{res_id}.xml"
                child = next(iter(metadata_el), None)
                if child is not None:
                    if _HAS_LXML:
                        target.write_bytes(LET.tostring(
                            child, xml_declaration=True, encoding="utf-8"))
                    else:
                        ET.ElementTree(child).write(
                            target, encoding="utf-8", xml_declaration=True)
                rel = str(target.relative_to(out))

            index_fh.write(
                f"{prefix}\t{ident}\t{datestamp}\t{repo_id or ''}\t{repo_name}\t{title}\t{rel}\n"
            )
            page_record_count += 1
            total += 1

        # Prefer the regex-recovered token (survives malformed pages).
        token = recovered_token
        if not token:
            token_el = root.find(".//o:resumptionToken", NS)
            token = (token_el.text or "").strip() if token_el is not None else ""

        print(f"  +{page_record_count} records (running total {total})")

        if not token:
            # End of harvest — clear checkpoint so next run starts fresh.
            if checkpoint_path.exists():
                checkpoint_path.unlink()
            break

        # Persist the token BEFORE making the next request so a crash there
        # can be resumed cleanly.
        import json
        checkpoint_path.write_text(json.dumps({
            "prefix": prefix, "set": set_spec,
            "from": from_date, "until": until_date,
            "token": token, "page": page,
        }))
        params = {"verb": "ListRecords", "resumptionToken": token}
        time.sleep(delay)

    index_fh.close()
    print(f"done. {total} records across {page} pages -> {out}")


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--prefix", default="oai_ead",
                   choices=["oai_ead", "oai_dc", "oai_dcterms"],
                   help="OAI metadata format (default: oai_ead)")
    p.add_argument("--set", dest="set_spec", default="full_as_oai",
                   help="OAI setSpec (default: full_as_oai)")
    p.add_argument("--out", default=str(Path(__file__).parent.parent / "data" / "cjh-oai"),
                   help="Output directory")
    p.add_argument("--from", dest="from_date", default=None,
                   help="OAI 'from' bound, YYYY-MM-DD or full UTC timestamp")
    p.add_argument("--until", dest="until_date", default=None,
                   help="OAI 'until' bound, YYYY-MM-DD or full UTC timestamp")
    p.add_argument("--delay", type=float, default=1.0,
                   help="Seconds between paginated requests (default: 1.0)")
    args = p.parse_args()

    out = Path(args.out).expanduser().resolve()
    harvest(args.prefix, args.set_spec, out, args.from_date, args.until_date, args.delay)


if __name__ == "__main__":
    main()
