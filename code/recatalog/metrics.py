"""Stage 5 — aggregate pilot cost/throughput metrics into the feasibility memo.

Reads whatever per-folder artifacts exist under data/recatalog/<folder>/ and a
hand-maintained data/recatalog/metrics_log.tsv where the agent records per-stage
effort as the pilot runs. Emits a Markdown summary + a full-collection projection.

metrics_log.tsv columns:
  folder, stage, engine, pages, unit_cost, cost_usd, tokens, minutes, note

- engine: tesseract | vision | transkribus | claude | human
- unit_cost: $/page or $/1k-tokens as applicable (0 for free engines)
- cost_usd: computed or measured dollar cost for the row (0 for Tesseract/Vision-MCP)
- tokens: Claude tokens used (0 otherwise)
- minutes: human minutes (segmentation/catalogue verification)

Usage:
  python code/recatalog/metrics.py --collection-folders 958 --collection-pages 250000
"""
from __future__ import annotations
import argparse, csv
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
BASE = ROOT / "data/recatalog"
LOG = BASE / "metrics_log.tsv"


def load_log() -> list[dict]:
    if not LOG.exists():
        return []
    with LOG.open() as fh:
        return list(csv.DictReader(fh, delimiter="\t"))


def num(x, default=0.0):
    try:
        return float(x)
    except (TypeError, ValueError):
        return default


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--collection-folders", type=int, default=958)
    ap.add_argument("--collection-pages", type=int, default=0,
                    help="est. total pages in full collection; 0 = extrapolate from pilot avg")
    args = ap.parse_args()

    rows = load_log()
    folders = sorted({r["folder"] for r in rows})
    pilot_pages = sum(num(r["pages"]) for r in rows if r["stage"] == "inventory")
    total_cost = sum(num(r["cost_usd"]) for r in rows)
    total_tokens = sum(num(r["tokens"]) for r in rows)
    total_minutes = sum(num(r["minutes"]) for r in rows)

    by_engine: dict[str, dict] = {}
    for r in rows:
        e = r.get("engine") or "-"
        d = by_engine.setdefault(e, {"pages": 0.0, "cost": 0.0, "tokens": 0.0, "min": 0.0})
        d["pages"] += num(r["pages"]); d["cost"] += num(r["cost_usd"])
        d["tokens"] += num(r["tokens"]); d["min"] += num(r["minutes"])

    per_page_cost = total_cost / pilot_pages if pilot_pages else 0
    per_page_min = total_minutes / pilot_pages if pilot_pages else 0

    out = ["# Feasibility & pricing — recatalog pilot", ""]
    out += [f"- Pilot folders: {len(folders)} ({', '.join(folders)})",
            f"- Pilot pages: {int(pilot_pages)}",
            f"- Total measured $ cost: ${total_cost:.2f}",
            f"- Total Claude tokens: {int(total_tokens):,}",
            f"- Total human minutes: {int(total_minutes)}",
            f"- **Per-page: ${per_page_cost:.4f} + {per_page_min:.2f} human-min**", ""]
    out += ["## By engine", "", "| engine | pages | $ | tokens | human-min |",
            "|---|---|---|---|---|"]
    for e, d in sorted(by_engine.items()):
        out.append(f"| {e} | {int(d['pages'])} | ${d['cost']:.2f} | {int(d['tokens']):,} | {int(d['min'])} |")

    coll_pages = args.collection_pages or int(per_page_cost and pilot_pages and
                 (args.collection_folders * (pilot_pages / max(len(folders), 1))))
    out += ["", "## Full-collection projection",
            f"- Folders: {args.collection_folders}", f"- Est. pages: {coll_pages:,}",
            f"- Projected $ (engines): ${per_page_cost * coll_pages:,.0f}",
            f"- Projected human hours: {per_page_min * coll_pages / 60:,.0f}", ""]

    (BASE / "feasibility_report.md").write_text("\n".join(out))
    print("\n".join(out))


if __name__ == "__main__":
    main()
