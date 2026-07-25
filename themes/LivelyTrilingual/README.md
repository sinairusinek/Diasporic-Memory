# LivelyTrilingual

A fork of the Omeka S **Lively** theme adding:
- EN / DE / HE language switching (default: English).
- Locale-aware rendering of property values with explicit `[Language TBA]` placeholders for missing translations.
- RTL layout for Hebrew.
- Switcher controls in both header and footer.

PI scope decisions (2026-06-08) baked in — see [project_trilingual_decisions](../../memory/project_trilingual_decisions.md).

## Install on the server

1. **Start from a copy of Lively.** On the server, in `/home/thedigin/omeka_s/themes/`:
   ```bash
   cp -R Lively LivelyTrilingual
   ```
2. **Apply patches from this directory.** Upload (or rsync) every file under this `LivelyTrilingual/` folder *over* the freshly-copied directory on the server:
   - `config/theme.ini` — name override.
   - `view/common/layout.phtml` — locale session + html lang/dir.
   - `view/common/lang-switcher.phtml` — the switcher partial.
   - `view/common/resource-values.phtml` — locale-aware value renderer.
   - `asset/css/rtl.css` — RTL overrides loaded only for `he`.
   - `language/he.po`, `language/de.po` — translation skeletons.
3. **Compile the `.po` files to `.mo`** (the binary form Omeka loads):
   ```bash
   cd /home/thedigin/omeka_s/themes/LivelyTrilingual/language
   msgfmt he.po -o he.mo
   msgfmt de.po -o de.mo
   ```
   If `msgfmt` isn't available on the server, compile locally and upload the `.mo` files.
4. **Activate** in Omeka admin: **Sites → Catalog → Theme → LivelyTrilingual**.

## Test plan

- Visit `https://omeka.dijest.net/s/catalog/?lang=en`, then `?lang=de`, then `?lang=he`.
- Confirm header reads in the chosen language; right-to-left layout kicks in for Hebrew.
- Open an item — fields without the chosen language show `[English TBA]` / `[German TBA]` / `[Hebrew TBA]`.
- Pre-existing language-neutral values (identifiers, dates) show in every locale.
- Switcher persists across navigation (cookie `site_lang`).

## Translation workflow

`he.po` and `de.po` are skeletons. Each `msgstr` is empty and needs translation. Workflow:

1. Open `he.po` in Poedit (or any PO editor).
2. Fill `msgstr` values.
3. Recompile to `he.mo`.
4. Upload, hard-refresh.
5. Repeat for `de.po`.

The skeletons cover the strings we found hard-coded in Lively; if you spot a missing one, add it as a new `msgid`/`msgstr` pair and the next compile will pick it up.

## Forking decisions

- We do NOT touch CSS files except adding `rtl.css`. All upstream Lively styles are inherited.
- Hard-coded English strings in Lively are wrapped in `$this->translate(...)` so PO files can intercept them.
- The resource-values renderer is intentionally a thin override; if Lively updates its version, you can re-pull and replay our small diff.
