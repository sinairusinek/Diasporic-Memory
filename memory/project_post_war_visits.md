---
name: project-post-war-visits
description: "Consolidated list of post-war (1945+) Jecke return-visits to Germany — first dedicated extraction, written to data/post_war_visits.tsv (2026-06-30)"
metadata:
  type: project
---

First consolidated extraction of post-war return-visits to Germany (the §1 "Visit" gesture / Heimat-criterion #1), pulled from existing corpus on 2026-06-30. Output: `data/post_war_visits.tsv` — 19 cases (PWV-01..19) with person, city, year, category, source_file, record_id, evidence. Prior partial passes existed (`data/cjh-oai/return_or_home.tsv` scored 228 CJH records; `letters_enriched.tsv` is_heimat_relevant notes) but were never aggregated into a visit list.

**Strongest actual-trip texts:**
- **Alfred Landsberg** "Deutschlandfahrt eines Israeli" (1951) + "Berlin 1956" + "Eine Fahrt nach Ostberlin" (~1959), G-F-0047-023 — primary diary-demo candidate, see [[project-landsberg-g047-23]].
- **Otto Mayer** F-0030: a whole post-war return cluster — 1950 Reisebericht, a SEPARATE 1951 handwritten Reisetagebuch, 1953 letters home, 1957 family-trip photos, 1957/1964 Andreas & Esther in Germany, Gertrud's 1951 visa. NOTE: corrects [[project-letters-extraction-status]] which logged "F-0030 Otto Mayer (0/5) WWI Feldpost only" as a negative control — that was a single sub-folder; the folder overall is rich post-war return material.
- **1969 "Deutschland, eine Winterreise"** Wizo Nahariya lecture (G-F-0113-041-R0016) — Heine echo, 1969 pilot anchor year.
- 1949 "erster Besuch des Kindes im Nachkriegsdeutschland" (G-F-0180-002) — earliest post-war return in corpus.
- Raga's 1957 Berlin visit report (G-F-0313-009); Schopler/Cologne emigrant-org + delegation visit (F-0276); Mannheimer/Worms 1964 invitation + 1985 honorary-citizenship refusal (F-0444); Berlinger Baden-Württemberg lecture tours (F-0422).
- Remigration: Leoni Frank-Landsberg (writes from Germany 1959/62), Wilma Adam.

**CJH 228 swept (2026-06-30):** the full CJH corpus (candidates.tsv `return_to_german` + return_or_home.tsv) yielded only ONE confirmed German-émigré return-to-Germany case — **Ernest W. Michel** (Mannheim 1923, Auschwitz survivor→US 1946; "Germany Revisited" JTA feature 1975; AJHS resource 6730) = PWV-20. Rejects worth remembering: Philip Friedman (born Lwów, JDC relief work not hometown return), John Stern (Hamburg-born but emigrated to Morocco — revises the Stern-Tagebuch diary candidate; it's a Morocco diary, off the return axis), Loeb family (18th-c. immigrants), Adolf Lorch/Blumenthal/Schauder (no documented return). CJH return-to-Germany signal is genuinely near-empty — the MTFN/Tefen holdings carry this corpus.

**Drive links resolved (2026-06-30):** added `drive_url` column to `data/post_war_visits.tsv` and clickable "Open scans in Drive" links in the exhibit cards. Drive scan folders are named `IL-MTFN-001-G-F-XXXX-N` UNPADDED (catalog pads: `0047-023` → Drive `0047-23`); the reliable lookup is exact-title folder search. There are TWO duplicate parallel folder trees (parents `1-4oOmBO58AMvdRjUQvxQlaywtXdgWT-a` = used canonically, and `1-03rmyQqU6NlJE5B0RGLlLzlP_FLaUr-`). Page-image filenames are `...-N_{seq}_{XXXX}.jpg` where trailing XXXX is NOT the folder (caused false matches). **12 of 20 cases link to scans; 8 are catalogue-only (no scan folder in Drive): the entire Otto Mayer F-0030 return cluster (sub-series 5/11/12/59 — only 0030-1/2/3 digitized), the 1949 child first-visit (0180-2), and Raga's Berlin letter (0313-9). The Mayer cluster is our 2nd-richest return source after Landsberg → digitization gap worth flagging to PI.** Access caveat: Drive folders live in user's My Drive; reviewers (Guy) need the parent shared or link-sharing on, else 404.

**Exhibit for Guy (2026-06-30):** built `mockups/return-visits/index.html` — a GitHub Pages gallery of all 20 cases, grouped (trip accounts / invitations-refusals / remigration / context), reusing the genre-mockup palette. Flagship card links into the existing `mockups/landsberg-deutschlandfahrt/` deep presentation (the only fully-transcribed item). Other cards are year-plate cards citing their MTFN folder (Drive retrieval) or CJH URL (Michel). Linked from `mockups/index.html`. Auto-deploys to sinairusinek.github.io/Diasporic-Memory/return-visits/ on push to mockups/ — NOT yet pushed (awaiting user). To enrich later: HTR the Mayer 1951 diary + 1969 Winterreise and give them their own deep mockups. Related: [[project-genre-demos]], [[reference-jeckearchive-github-pages]].

Related: [[project-what-we-are-looking-for]], [[feedback-heimat-relevance-criteria]], [[project-cjh-shortlist]].
