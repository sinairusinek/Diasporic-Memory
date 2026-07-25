---
name: project-what-we-are-looking-for
description: Structured target-corpus definition for the diasporic-memory project — scope, document types, thematic axes, filters, retrieval vocabulary, and signal-computation rules
metadata:
  type: project
---

# What we are looking for

A structured definition of the target corpus for the diasporic-memory project. Sections are independent and meant to be composed into prompts:

1. **Scope** — what the project is about (one paragraph).
2. **Document types** — neutral genre vocabulary (what *form* a record takes).
3. **Thematic axes** — what *content* makes a record relevant.
4. **Contextual subgenres** — recurring situations that promote a record to first-tier.
5. **Filters** — geographic / date / vector rules that exclude otherwise-matching records.
6. **Retrieval vocabulary** — multilingual keyword tables organized by axis.
7. **Signal-computation rules** — implementation conventions for scoring and propagation.

---

## 1. Scope

This is a project about **diasporic memory**. The target documents are first-person and interpersonal records in which German-Jewish émigrés engage with their towns of origin in **Germany within its 1937 borders**. The intellectual core is how diasporic communities reconstruct, narrate, and re-visit places they were forced to leave — return-visit accounts in particular are a thin and dispersed source genre that has not been systematically aggregated.

Three core gestures define in-scope material:

- **Visit** — post-emigration return journeys to the home town.
- **Reminisce** — retrospective writing about the home town from the diaspora.
- **Discuss** — correspondence in which the home town is a topic (with family, friends, classmates, neighbors, municipal authorities).

Discourse *about* visits (pro/contra, refusal of invitations, critique of reconciliation narratives) is also in scope — it is memory work, not an exclusion.

---

## 2. Document types

Neutral form categories. A document type alone does not make a record in-scope — it must also carry a thematic signal (§3) or sit in a recognized contextual subgenre (§4).

- Memoir / autobiography / reflective essay
- Personal correspondence (private letters)
- Institutional / municipal correspondence (restitution, invitation, archival)
- Diary / travel journal
- Oral history interview / transcript
- Photo album with annotations
- Manuscript (unpublished prose)

Personal-papers archival structure (Personal Papers, Familiensammlung, Nachlass, עיזבון) is itself a weak positive signal because it predicts the presence of the above types.

---

## 3. Thematic axes

### 3.1 Heimat (primary axis)

Local affinity for the city of origin — the intimate, hometown sense of *Heimat*. Following Miron's "Between the Vaterland and Local Memory," this is the project's **main target**: it proved "far deeper and more resilient" than nation-level loyalty and persists across generations.

Sub-dimensions, all in scope when explicit:

- **Hometown / local landscape** — streets, neighborhoods, named places. The primary axis.
- **German language and literary canon as remaining homeland** — e.g. Ben-Chorin's "I have never emigrated from the language"; Werner Kraft's "live and conduct my life within the German spirit." Passing Goethe/Fontane citations are NOT auto-Heimat (see [[feedback-no-forced-heimat-framing]]).
- **German nature / landscape** — especially local (Black Forest, Alps, forests, lakes); also émigrés reading foreign landscapes through German Romanticism (Spitzer on Bolivian mountains).

Related/alternative concepts to explore in retrieval: *Heimatstadt, Geburtsstadt, Herkunftsstadt, Lokalpatriotismus, verlorene Heimat, einstiges Zuhause*.

### 3.2 Vaterland (secondary axis, code separately)

Patriotic loyalty to Germany-as-nation (the "deutsche Heimat" of pre-1933 nationalist register). Faded fast after 1933 and typically appears only in older-generation writers, often in retrospect critically or with embarrassment.

In scope, but **do not collapse with Heimat** — keep the two as distinct evidentiary categories.

---

## 4. Contextual subgenres

Recurring situations that promote a record to a first-tier signal even if the surface text looks mundane.

- **Reparations correspondence with German municipal authorities (1946+)** — restitution, property, cemetery, memorial. Even "dry legal" letters generated emotional reckoning with the hometown (Schwab/Hanau case). Treat as memory work.
- **Municipal visitor program letters and invitations** — date anchors: Heilbronn ~1955 (Paul Meyle); institutionalized 1960s; **Berlin program launched 1969**; 1970s–80s peak; post-1990 East German cities. *Aufbau* travel-to-Germany ads appear late 1960s. Validates the 1969 pilot year.
- **Local German memory agents** — mayors, town councillors, archivists, educators, amateur local historians (e.g. Oskar Schenk, Hanau) writing to émigrés. Strong signal even when the émigré's own voice is muted in the folder.
- **Family correspondence clusters driven by dispersal** — siblings/parents scattered across continents post-1933. Miron theorizes this as a leading German-Jewish memory genre; cross-continental family-letter clusters are first-tier even when individual letters look routine.
- **Mixed and refusal responses** — angry rejections of municipal invitations, critique of German hosts' reconciliation narratives, refusal to visit. Memory work, not exclusions.

---

## 5. Filters

### 5.1 Geographic

Towns of origin must lie within **Germany in its 1937 borders**. Austria and broader Central Europe are out of scope for the hometown axis.

### 5.2 Date

**Drop records earlier than 1933.** The target is German Jews who *emigrated* and then visited / reminisced / corresponded about their hometown. Pre-1933 artifacts (childhood letters, WWI-era diaries, Kaiserzeit photos) are life-in-Germany material, not diasporic memory.

Implementation: extract all 4-digit years (1800–2099) from `creation_date` and description text; keep only items whose **max year ≥ 1933**. Drop undated items by default.

**Exception A — memoir-tagged items are date-exempt.** Retrospective *Erinnerungen / Memoiren / Zikhronot / זכרונות / memoir* are by definition written from the diaspora about the lost home; their content years are usually pre-emigration but the *work* is the genre we want. Keep any item whose signals include `memoir`, regardless of date or dating status.

**Exception B — folder-level signal propagation** (see §7.2).

### 5.3 Vector (Palestine / other-country outbound)

Travel diaries, journey accounts, and visit records whose destination is **Palestine / Eretz Israel / Israel** are the *opposite* vector (the leaving, not the return/reminisce/re-encounter with the hometown).

Drop when **all** hold:

- The item's only signals are `visit` or `diary`.
- The text contains an outbound cue: *nach Palästina / nach Israel / to Palestine / to Israel / לפלשתינה / לארץ ישראל / Auswanderung / עליה / emigration*.
- The text contains **no** return cue: *zurück nach, Rückkehr, Rückreise, back to [German place], visited his/her hometown, ביקור בגרמניה / וינה / …, חזרה ל…*.

Example to exclude: Goetz's *Reisetagebuch nach Palästina*.

Memoir, Heimat, hometown, or correspondence signals **always override** this filter — they keep the record in scope regardless of destination wording.

---

## 6. Retrieval vocabulary

Multilingual keyword sets, organized by axis. Use these to build search filters and rank candidates. EN / DE / HE per row where applicable.

### 6.1 Document type signals

| Axis | EN | DE | HE |
|---|---|---|---|
| Memoir | memoir, autobiography, reminiscences | Memoiren, Erinnerungen, Lebenserinnerungen | זכרונות, אוטוביוגרפיה |
| Correspondence | correspondence, letters | Briefe, Korrespondenz, Briefwechsel | מכתבים, התכתבות |
| Diary / journal | diary, journal | Tagebuch | יומן |
| Oral history | oral history, interview | Interview | ראיון, היסטוריה בעל-פה |
| Personal papers | personal papers | Nachlass, Familiensammlung | עיזבון |

### 6.2 Heimat / hometown signals

| Axis | EN | DE | HE |
|---|---|---|---|
| Hometown concept | hometown, place of origin | Heimat, Heimatstadt, Geburtsort, Geburtsstadt, Herkunftsstadt, einstiges Zuhause, verlorene Heimat | מולדת, עיר הולדת |
| Local patriotism | local patriotism | Lokalpatriotismus | — |
| Return / visit | return, visit, going back | Rückkehr, Rückreise, zurück nach, Besuch, Reise | חזרה, ביקור, נסיעה חזרה |

### 6.3 Vaterland signals (code separately)

| EN | DE | HE |
|---|---|---|
| fatherland, German nation | Vaterland, deutsche Heimat, Deutschtum | מולדת גרמנית |

### 6.4 Outbound-vector terms (used by §5.3 filter)

| EN | DE | HE |
|---|---|---|
| to Palestine, to Israel, emigration | nach Palästina, nach Israel, Auswanderung | לפלשתינה, לארץ ישראל, עליה |

---

## 7. Signal-computation rules

### 7.1 Where to compute signals

Compute signals over the **folder catalog row**: 245$a title, drive title, description, keywords. Item-level descriptions are often mechanical ("manuscript, 13 pages", "photo of article") and miss the folder-level genre cue (e.g. `Hecker Max Mordechai - זכרונות`).

### 7.2 Folder → item propagation

Every item under a signal-bearing folder inherits the folder's signals. Track provenance in a `signal_source` column with values `item` / `folder` / `item+folder` so curation can see why a record was kept.

### 7.3 Date extraction

Extract all 4-digit years (1800–2099) from `creation_date` and description text. Use **max year** for the §5.2 floor. Drop undated items unless they carry a `memoir` signal.

### 7.4 Vector filter

Apply §5.3 only when the item carries no memoir / Heimat / hometown / correspondence signal — those four always override.

---

## Cross-references

- [[project-cjh-oai-lbi-pending]] — current working CJH corpus.
- [[feedback-no-forced-heimat-framing]] — only label explicit Heimat signals; atmosphere/literary refs alone do not qualify.
- [[feedback-heimat-relevance-criteria]] — PI-confirmed in/out boundary for the corpus.
