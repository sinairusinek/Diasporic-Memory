# Trilingual public site — implementation plan

## Scope decisions (PI, 2026-06-08)

1. **Default language**: English (when no user preference).
2. **Missing-translation handling**: show explicit placeholder `[Hebrew TBA]` / `[German TBA]` / `[English TBA]`. Do not silently fall back to another language — placeholders surface what needs curation.
3. **Switcher placement**: top header **and** footer.

## What Lively gives us today

From inspecting `themes/Lively/config/theme.ini`:
- **Zero i18n config.** No locale settings, no language switcher hook, no `language/` folder mentioned in helpers.
- All theme strings (button labels, "Browse series", etc.) are hard-coded English in the PHP view templates.
- Resource-page blocks are configured generically — they render whatever values an item has, with no per-locale filter.

So this is a real theme fork, not just settings tweaks. We **fork Lively into `LivelyTrilingual`** so upstream Lively updates don't blow it away.

## Implementation outline

### 1. Fork the theme

In `omeka_s/themes/`:

```bash
cp -R Lively LivelyTrilingual
# Edit LivelyTrilingual/config/theme.ini:
#   name = "Lively Trilingual"
```

In admin → Sites → Catalog → Theme: switch to "Lively Trilingual".

### 2. Locale management — a header session/cookie

Create `LivelyTrilingual/view/common/layout.phtml` (override Lively's). At top of file:

```php
<?php
$locale = $this->params()->fromQuery('lang')
       ?? ($_COOKIE['site_lang'] ?? null)
       ?? 'en';
if (!in_array($locale, ['en', 'de', 'he'])) { $locale = 'en'; }
if (($_COOKIE['site_lang'] ?? null) !== $locale) {
    setcookie('site_lang', $locale, time()+86400*365, '/');
}
// Make available to templates
$this->vars()->lang = $locale;
$this->layout()->lang = $locale;
// Set <html lang="..." dir="...">
$this->layout()->htmlLang = $locale;
$this->layout()->htmlDir  = $locale === 'he' ? 'rtl' : 'ltr';
?>
```

### 3. Switcher components

Two partials, used in both header and footer:

`LivelyTrilingual/view/common/lang-switcher.phtml`:
```php
<?php
$current = $this->lang ?? 'en';
$base = $this->serverUrl(true);
$qs = $_SERVER['QUERY_STRING'] ?? '';
parse_str($qs, $q);
$buttons = ['en' => 'EN', 'de' => 'DE', 'he' => 'HE'];
?>
<nav class="lang-switcher" aria-label="<?= $this->translate('Language') ?>">
  <?php foreach ($buttons as $code => $label): ?>
    <?php $q['lang'] = $code; $url = strtok($base, '?') . '?' . http_build_query($q); ?>
    <a class="<?= $current === $code ? 'active' : '' ?>" href="<?= $url ?>"><?= $label ?></a>
  <?php endforeach; ?>
</nav>
```

Include it twice: once in the header partial, once in the footer partial.

### 4. Render values with locale + placeholder

Override `LivelyTrilingual/view/common/resource-values.phtml` (or whichever Lively partial renders `displayValues()`). For each property:

```php
<?php
$lang = $this->lang ?? 'en';
$placeholderMap = ['en' => '[English TBA]', 'de' => '[German TBA]', 'he' => '[Hebrew TBA]'];
foreach ($resource->values() as $term => $entry) {
    $byLang = [];
    foreach ($entry['values'] as $v) {
        $vl = $v->lang() ?: ''; // empty string for no-language values
        $byLang[$vl][] = $v;
    }
    if (!empty($byLang[$lang])) {
        // Show values matching current lang
        $toRender = $byLang[$lang];
    } elseif (!empty($byLang[''])) {
        // Fall back to no-language values (assumed neutral, usable in any locale)
        $toRender = $byLang[''];
    } else {
        // Render placeholder for this language
        echo '<div class="value placeholder">' . $placeholderMap[$lang] . '</div>';
        continue;
    }
    foreach ($toRender as $v) {
        echo $v->asHtml(); // or whatever rendering Lively uses
    }
}
?>
```

**Key rule:** values with no `@language` tag are treated as language-neutral and shown in all locales (e.g. identifiers, dates, URLs). Only language-tagged values trigger the placeholder logic.

### 5. UI string translation (Lively's hard-coded English)

Lively has English strings hard-coded in its `.phtml` files. We need to wrap each in `$this->translate('...')`. Examples found in the theme:
- "Browse series"
- "Browse folders"
- "Persons"
- "Places"
- "Bibliography"
- Banner text (if used)
- Footer titles

Then add a `LivelyTrilingual/language/` folder with:
- `de.po` / `de.mo`
- `he.po` / `he.mo`

Use the `Internationalisation` module by Daniel Berthereau if installed; otherwise generate `.mo` files with `msgfmt` from `.po` and place them in the theme's language folder.

### 6. Browse-page filters

Lively's `browse_layout` setting (grid/list/toggle) is independent of language. The values shown on each card need the same locale logic from §4. Override `LivelyTrilingual/view/common/resource-card.phtml` (or similar) with the locale-aware renderer.

### 7. CSS for RTL

Hebrew is right-to-left. Lively's CSS is LTR-only.

In `LivelyTrilingual/asset/css/`, add an `rtl.css` that flips margins, padding, and text-align for `.lang-he` (or use `[dir="rtl"]` selectors). Inject via:

```php
<?php if (($this->lang ?? '') === 'he'): ?>
  <?= $this->headLink(['rel' => 'stylesheet', 'href' => $this->assetUrl('css/rtl.css')]) ?>
<?php endif; ?>
```

## Effort estimate

| Task | Hours |
|---|---:|
| Fork theme + register | 0.5 |
| Locale management + switcher partials | 1 |
| Resource-value renderer with placeholder | 1.5 |
| Translate hard-coded English strings + .po/.mo files | 2 |
| RTL CSS | 1 |
| Testing across 3 locales × multiple page types | 1 |
| **Total** | **7** |

This is a focused-coding-session, not a few-minute job. Can be done across one or two work sessions.

## Out of scope (future)

- **Auto-translation** of missing values via DeepL/MT — explicitly excluded by PI: placeholders surface gaps rather than mask them. If you later want to seed the placeholders from MT, that's a separate batch job.
- **Admin UI locale switching** — admin uses Omeka core's locale handling, separate concern.
- **Per-user persistent language preference** — current plan uses cookie scoped to the site, which is the standard pattern. Adding per-user settings means tying into Omeka's user-preferences API (extra scope).

## Dependencies / sequencing

1. Finish dedupe/merge (done — 135/135 merged + backlinks fixed).
2. Install CleanUrl module (instructions in [CLEANURL_INSTALL.md](CLEANURL_INSTALL.md)) — doesn't block, but cleaner URLs make the language switcher's URL-param flow nicer.
3. Then this trilingual fork.

When you're ready to start the fork, the simplest opener is: I write the patched files locally and you copy them up to the server's `themes/LivelyTrilingual/`, OR I draft them as a Git-trackable mini-repo so changes are reviewable.
