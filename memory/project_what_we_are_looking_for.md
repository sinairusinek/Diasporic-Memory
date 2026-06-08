---
name: project-what-we-are-looking-for
description: The kinds of source documents this project (diasporic memory of German-Jewish immigrants) is looking for
metadata:
  type: project
---

This is a project about **diasporic memory**. The target documents are first-person and interpersonal records in which German-Jewish immigrants engage with their towns of origin in Central Europe — concretely, materials that:

1. **Describe visits** by émigrés back to their German/Austrian/Central European home towns (post-emigration return journeys, sometimes decades later).
2. **Reminisce** about those home towns from the diaspora (memoirs, autobiographies, reflective essays, oral histories).
3. **Discuss** the home towns within correspondence — letters between émigrés, letters to family/friends who stayed or also emigrated, letters to/from town authorities, gymnasium classmates, neighbors.

Genres of interest: memoirs, manuscripts, personal correspondence, diaries, oral history interviews, photo albums with annotations, travel journals — anything that surfaces the émigré–hometown relationship as remembered or re-encountered.

**Why:** The intellectual core is how diasporic communities reconstruct, narrate, and re-visit places they were forced to leave — return-visit accounts in particular are a thin and dispersed source genre that hasn't been systematically aggregated.

**How to apply:** When evaluating any candidate dataset (CJH OAI harvest, DigiBaeck, Landecker Digital Memory Lab database, Jecke Archive, future sources), filter and rank records by signals like: "memoir", "Memoiren", "Erinnerungen", "זכרונות", "correspondence", "Briefe", "letters", "diary", "Tagebuch", "יומן", "Heimat", "Heimatstadt", "Geburtsort", "מולדת", "return", "visit", "Reise", "Besuch", "ביקור", "נסיעה", presence of a single named Central European hometown, and personal-papers structure (Personal Papers, Familiensammlung, Nachlass, עיזבון). See [[project-cjh-oai-lbi-pending]] for the current working corpus.

**Date filter — drop records earlier than 1933, with two exceptions.** Historically the target is German Jews who *emigrated* and then visited / reminisced about / corresponded with their hometown. Pre-1933 artifacts (childhood letters, WWI-era diaries, family heirlooms, photos from the Kaiserzeit) are life-in-Germany material, not diasporic memory, even when they hit memoir/diary/correspondence signals. Implementation: extract all 4-digit years (1800–2099) from creation_date and description text; keep only items whose **max year ≥ 1933**. Drop undated items by default.

**Exception 1 — memoir-tagged items are date-exempt.** Retrospective *Erinnerungen / Memoiren / Zikhronot / זכרונות / memoir* are by definition written from the diaspora about the lost home; their *content years* are usually pre-emigration but the *work* is exactly the genre we want. Keep any item whose signals include `memoir`, regardless of date or whether it's dated at all.

**Exception 2 — propagate folder-level signals to items.** Sub-series titles often carry the genre signal (e.g. `Hecker Max Mordechai - זכרונות`) while individual item descriptions are mechanical ("manuscript, 13 pages", "photo of article"). Compute signals on the *folder catalog* row (245$a title, drive title, descriptions, keywords) and mark every item under that folder as inheriting that signal. Track the source in a `signal_source` column (`item` / `folder` / `item+folder`) so curation can see why something was kept.

**Exclusion — immigration-to-Palestine vector is OUT of scope.** Travel diaries, journey accounts, and visit records whose destination is Palestine / Eretz Israel / Israel are the *opposite* vector (the leaving, not the return/reminisce/re-encounter with the hometown). Concretely: when an item's only signals are `visit` or `diary` AND the text contains "nach Palästina / nach Israel / to Palestine / to Israel / לפלשתינה / לארץ ישראל / Auswanderung / עליה / emigration" *without* a return cue ("zurück nach", "Rückkehr", "Rückreise", "back to [Central European place]", "visited his/her hometown", "ביקור בגרמניה/וינה/...", "חזרה ל..."), drop it. Example to exclude: Goetz's *Reisetagebuch nach Palästina*. Memoir/Heimat/hometown/correspondence signals are never overridden by this filter — they keep the record in scope regardless of destination wording.
