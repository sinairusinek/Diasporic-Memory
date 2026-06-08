"""Render ead_candidates.tsv as a self-contained HTML browse-and-filter report.

Output: data/cjh-oai/ead_candidates.html
Open it in any browser; no server needed.

Features:
  - Click column headers to sort
  - Free-text filter box (matches title / origination / snippet / geognames)
  - Quick toggles to show only records with each strong signal
  - Snippet column shows the EAD evidence quote
  - Title links to the CJH ArchivesSpace finding aid
"""
from __future__ import annotations

import csv
import html
import json
from pathlib import Path


def main():
    src = Path(__file__).parent.parent / "data" / "cjh-oai" / "ead_candidates.tsv"
    dst = src.with_suffix(".html")
    rows = list(csv.DictReader(src.open(encoding="utf-8"), delimiter="\t"))

    # Compact each row for the client-side table.
    data = []
    for r in rows:
        data.append({
            "score":   int(r["score"]),
            "repo":    r["repo_id"],
            "resid":   r["resource_id"],
            "title":   r["title"],
            "creator": r["origination"],
            "birth":   r["birth"] or "",
            "max_year": r["max_year"],
            "bp":      r["birthplace"],
            "ret_de":  int(r["ret_de"]),
            "born_de": int(r["born_de"]),
            "heimat":  int(r["heimat"]),
            "ce":      int(r["ce_return_hit"]),
            "pal":     int(r["palestine_hit"]),
            "lang":    r["langmaterial"],
            "geo":     r["geognames"],
            "snippet": r["snippet"],
            "url":     r["url"],
        })

    body = f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>CJH Jecke candidates ({len(data)})</title>
<style>
  body {{ font-family: -apple-system, system-ui, sans-serif; margin: 1rem;
          font-size: 13px; color: #222; }}
  header {{ display: flex; align-items: baseline; gap: 1rem; flex-wrap: wrap;
            margin-bottom: .8rem; }}
  h1 {{ font-size: 1.2rem; margin: 0; }}
  .controls {{ display: flex; gap: .6rem; flex-wrap: wrap; align-items: center;
               margin-bottom: .8rem; }}
  input[type=search] {{ padding: .35rem .5rem; width: 22rem;
                        font-size: 13px; border: 1px solid #aaa; border-radius: 3px; }}
  label.chip {{ background: #eef; padding: .25rem .55rem; border-radius: 3px;
                cursor: pointer; user-select: none; border: 1px solid #ccd; }}
  label.chip.on {{ background: #cce; border-color: #88a; }}
  table {{ border-collapse: collapse; width: 100%; }}
  th, td {{ padding: .35rem .5rem; vertical-align: top; border-bottom: 1px solid #eee;
            text-align: left; }}
  th {{ background: #f7f7f7; cursor: pointer; position: sticky; top: 0;
        border-bottom: 2px solid #ddd; user-select: none; }}
  th:hover {{ background: #eee; }}
  td.score {{ font-weight: 600; text-align: right; }}
  td.snippet {{ font-style: italic; color: #555; max-width: 30rem; }}
  td.title {{ max-width: 22rem; }}
  td.creator {{ font-size: 12px; color: #555; max-width: 14rem; }}
  .badge {{ display: inline-block; padding: 1px 5px; border-radius: 3px;
            font-size: 11px; margin-right: 2px; }}
  .b-ger {{ background: #d4f0d4; color: #060; }}
  .b-non {{ background: #f0d4d4; color: #600; }}
  .b-unk {{ background: #eee; color: #555; }}
  .b-ret {{ background: #fff2c0; color: #663; }}
  .b-born {{ background: #cfe1ff; color: #035; }}
  .b-heimat {{ background: #ffd5e8; color: #804; }}
  .b-pal {{ background: #ddd; color: #555; font-style: italic; }}
  a {{ color: #246; text-decoration: none; }}
  a:hover {{ text-decoration: underline; }}
  .count {{ color: #666; font-size: 12px; }}
</style>
</head>
<body>
<header>
  <h1>CJH Jecke candidates</h1>
  <span class="count" id="count"></span>
</header>
<div class="controls">
  <input id="q" type="search" placeholder="Filter titles, creators, geos, snippets…" autofocus>
  <label class="chip" data-flag="bp_ger">birthplace = German</label>
  <label class="chip" data-flag="ret_de">return-to-German</label>
  <label class="chip" data-flag="born_de">born-in-German phrase</label>
  <label class="chip" data-flag="heimat">Heimat/hometown</label>
  <label class="chip" data-flag="no_pal">no Palestine vector</label>
</div>
<table>
  <thead><tr>
    <th data-key="score">Score</th>
    <th data-key="title">Title</th>
    <th data-key="creator">Creator</th>
    <th data-key="birth">Birth</th>
    <th data-key="max_year">Max yr</th>
    <th data-key="bp">Birthplace</th>
    <th data-key="signals">Signals</th>
    <th data-key="lang">Lang</th>
    <th data-key="geo">Geo</th>
    <th data-key="snippet">Evidence snippet</th>
  </tr></thead>
  <tbody id="tbody"></tbody>
</table>
<script>
const data = {json.dumps(data, ensure_ascii=False)};
let sortKey = 'score'; let sortDir = -1;
const flags = new Set();
const q = document.getElementById('q');
const tbody = document.getElementById('tbody');
const count = document.getElementById('count');

function badge(cls, label) {{ return `<span class="badge ${{cls}}">${{label}}</span>`; }}

function render() {{
  const needle = q.value.trim().toLowerCase();
  let rows = data.filter(r => {{
    if (needle) {{
      const hay = (r.title + ' ' + r.creator + ' ' + r.geo + ' ' + r.snippet).toLowerCase();
      if (!hay.includes(needle)) return false;
    }}
    if (flags.has('bp_ger') && r.bp !== 'german') return false;
    if (flags.has('ret_de') && !r.ret_de) return false;
    if (flags.has('born_de') && !r.born_de) return false;
    if (flags.has('heimat') && !r.heimat) return false;
    if (flags.has('no_pal') && r.pal) return false;
    return true;
  }});
  rows.sort((a, b) => {{
    let av = a[sortKey], bv = b[sortKey];
    if (sortKey === 'signals') {{ av = a.ret_de*10 + a.born_de*5 + a.heimat*3; bv = b.ret_de*10 + b.born_de*5 + b.heimat*3; }}
    if (typeof av === 'number') return (av - bv) * sortDir;
    return String(av).localeCompare(String(bv)) * sortDir;
  }});
  count.textContent = `${{rows.length}} of ${{data.length}} records`;
  tbody.innerHTML = rows.map(r => {{
    const bpCls = r.bp === 'german' ? 'b-ger' : r.bp === 'non_german' ? 'b-non' : 'b-unk';
    let sig = '';
    if (r.ret_de) sig += badge('b-ret', `ret→DE ×${{r.ret_de}}`);
    if (r.born_de) sig += badge('b-born', `born→DE ×${{r.born_de}}`);
    if (r.heimat) sig += badge('b-heimat', `Heimat ×${{r.heimat}}`);
    if (r.ce) sig += badge('b-ret', 'CE return');
    if (r.pal) sig += badge('b-pal', 'Palestine');
    return `<tr>
      <td class="score">${{r.score}}</td>
      <td class="title"><a href="${{r.url}}" target="_blank">${{escapeHtml(r.title)}}</a></td>
      <td class="creator">${{escapeHtml(r.creator)}}</td>
      <td>${{r.birth}}</td>
      <td>${{r.max_year}}</td>
      <td><span class="badge ${{bpCls}}">${{r.bp}}</span></td>
      <td>${{sig}}</td>
      <td>${{escapeHtml(r.lang)}}</td>
      <td>${{escapeHtml(r.geo)}}</td>
      <td class="snippet">${{escapeHtml(r.snippet)}}</td>
    </tr>`;
  }}).join('');
}}
function escapeHtml(s) {{ return String(s||'').replace(/[&<>"']/g, c => ({{'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}})[c]); }}

document.querySelectorAll('th').forEach(th => th.addEventListener('click', () => {{
  const k = th.dataset.key;
  if (sortKey === k) sortDir = -sortDir; else {{ sortKey = k; sortDir = -1; }}
  render();
}}));
document.querySelectorAll('.chip').forEach(c => c.addEventListener('click', () => {{
  const f = c.dataset.flag;
  if (flags.has(f)) {{ flags.delete(f); c.classList.remove('on'); }}
  else {{ flags.add(f); c.classList.add('on'); }}
  render();
}}));
q.addEventListener('input', render);
render();
</script>
</body>
</html>
"""
    dst.write_text(body, encoding="utf-8")
    print(f"wrote {dst} ({len(data)} rows)")


if __name__ == "__main__":
    main()
