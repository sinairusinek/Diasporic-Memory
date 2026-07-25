# Span-level annotation scheme — "Juden kehren zurück nach Deutschland" (Aufbau, 1946–1998)

Unit of annotation: a **text span** of any length (one word → whole article), on the
German verbatim OCR. Spans may nest and overlap. Hebrew translations inherit the
German span's tags by alignment; they are not annotated independently.

Each span carries:
- exactly one **F1 span-type**
- exactly one **F2 time-layer**
- zero or one **F3 voice**
- zero or one **F4 stance** (only where evaluative language is present)
- one or more **T theme tags** (the substantive facet)

---

## F1 · Span-type (what kind of utterance this is)

| Tag | Description |
| :-- | :-- |
| `type:narration` | Reported events, third-person journalistic account |
| `type:testimony` | First-person experience (the Ich-Berichte: arts. 12, 24, 38, 41) |
| `type:quotation` | Speech attributed to a named source (mayor, returnee, cardinal) |
| `type:evaluation` | The paper's or author's own judgement / editorial comment |
| `type:document` | Reproduced text: open letter, appeal, thank-you note, statistic table |
| `type:paratext` | Headline, byline, dateline, caption |
| `type:noise` | OCR garble, advertisement, or bleed-through from an adjacent column (see art. 41) — excluded from analysis but must be marked so it is not silently read as content |

## F2 · Time-layer (which moment the span refers to, not when it was printed)

`time:pre1933` · `time:1933-1945` (persecution, flight) · `time:exile` (the years abroad) ·
`time:return-event` (the journey/visit itself) · `time:postreturn` (life after) ·
`time:publication-present` (the paper's own now) · `time:prospective` (planned, hoped, feared)

## F3 · Voice (whose position the span articulates)

`voice:returnee` · `voice:visitor` (invited guest, not resettled) · `voice:refuser` ·
`voice:german-official` · `voice:german-public` · `voice:jewish-organisation` ·
`voice:editorial` · `voice:scholar`

## F4 · Stance toward return (annotate only on explicit evaluative language)

`stance:affirming` · `stance:ambivalent` · `stance:rejecting` · `stance:contested`
(the span itself stages a disagreement)

---

## T · Themes

Seven groups. Sub-tags are the working level; the group is a roll-up for querying.

### T1 Form of the return
- `T1.1 resettlement` — permanent remigration
- `T1.2 visit` — bounded stay, return ticket assumed
- `T1.3 professional-mission` — return in an official role (Döblin as French army officer, art. 21)
- `T1.4 refusal` — the decision *not* to go, articulated as such
- `T1.5 deliberation` — weighing, hesitating, delaying (Evelyn Pearl's "langes Zaudern", art. 50)
- `T1.6 repeat-return` — a second or later journey; the visit that becomes a habit

### T2 Apparatus and mediation
- `T2.1 municipal-invitation` — Besuchsprogramm / Begegnungswoche as institution
- `T2.2 finance` — who pays: fares, hotel, the Göppingen budget rising 105,000 → 225,000 DM (art. 28)
- `T2.3 logistics-borders` — visas, occupation zones, transport, charter aircraft
- `T2.4 protocol` — reception, Rathaus, mayor's address, VIP lounge, banquet
- `T2.5 broker` — the individual who makes it happen (Uzarski, Dieter Arntz, Karl Goldsmith)
- `T2.6 selection` — who gets invited, how many, and who is left out

### T3 Heimat and place
Apply `T3.1` **only** where an explicit Heimat/Vaterstadt/alte Heimat/מולדת lexeme or an
unambiguous equivalent is present. Atmosphere and mere place-naming are not enough.
- `T3.1 heimat-claim` — the place named as home
- `T3.2 topography` — streets, houses, school, the Rhine trip, sites of childhood
- `T3.3 ruin-and-rebuilding` — destroyed, rebuilt, unrecognisable, "das neue Gesicht"
- `T3.4 absence` — what is *not* there: no relatives, no houses, not even the graves (art. 41)
- `T3.5 exile-geography` — the place returned *from* (London, Istanbul, Mexico, Tangier, Haifa)

### T4 Reckoning
- `T4.1 reconciliation` — Versöhnung, Geste, outstretched hands
- `T4.2 restitution` — Wiedergutmachung, pension, recognised service, moral restitution
- `T4.3 persisting-antisemitism` — the Frings affair (art. 11); "das Gift des Judenhasses"
- `T4.4 taboo` — the norm that there is no return for Jews (the AJR platform, art. 1)
- `T4.5 legitimacy-debate` — public argument over whether one should go (art. 27)
- `T4.6 unforgiving-formula` — the recurrent "wir vergeben, aber vergessen können wir nicht" (art. 47)
- `T4.7 encounter` — face-to-face meeting with Germans: old friends, hosts, youth, clergy

### T5 Life course and vocation
- `T5.1 career-restart` — chair, editorship, Intendanz, bank partnership
- `T5.2 recognition` — honorary citizenship, prizes, Ehrenbürger (art. 39)
- `T5.3 late-life` — Lebensabend, old-age home, returning at great age (art. 9, 26)
- `T5.4 death-and-burial` — Nachruf, funeral, buried in Germany (arts. 44, 20, 40)
- `T5.5 family-fate` — what happened to the relatives; researching their deaths

### T6 Memory and transmission
- `T6.1 memory-institution` — Germania Judaica, Archiv der Erinnerung, Budge-Stiftung
- `T6.2 object-return` — a thing that travels back: the 1826 Tora (art. 38), the looted Aktions-Buch (art. 5), 60 paintings (art. 4)
- `T6.3 published-account` — the return as book/film/memoir under review (arts. 16, 30, 45)
- `T6.4 breaking-silence` — Verdrängung ending, speech becoming possible
- `T6.5 intergenerational` — addressing German youth, the next generation

### T7 Collective frame
- `T7.1 demography` — counts of returnees; Maor's figures; deaths outpacing arrivals (art. 14)
- `T7.2 community-viability` — Jewish life in Germany today, is there a future
- `T7.3 israel-vector` — Palestine/Israel as the alternative destination; Six-Day War as turning point; Israelis returning as Israelis (art. 35)
- `T7.4 german-politics` — occupation, zones, Cold War, GDR/Soviet sector, reunification
- `T7.5 emotion-register` — bitterness, dread, joy, the explicit mixture (Lore May Rasmussen, art. 48)

---

## Annotation rules

1. **Tag the shortest span that carries the theme.** A whole paragraph gets a theme tag
   only when the theme is distributed across it, not when one clause carries it.
2. **Overlap freely across facets, sparingly within one.** "Wir vergeben, aber vergessen
   können wir nicht" is `T4.6` + `T4.1` + `T7.5` on the same span — that is the point.
3. **Nesting is expected.** An article-length `type:testimony` span contains sentence-level
   theme spans; both are kept.
4. **Do not tag on translation evidence.** If the German OCR is unreadable and only the
   Gemini Hebrew renders the passage, mark `type:noise` and record the reading as a note.
   The Google translation is unreliable and is never annotation evidence.
5. **Absence of a tag is data.** A visit report with no `T4.1` is a finding.
