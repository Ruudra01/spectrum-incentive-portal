# Spectrum Incentive Portal

Internal field-agent incentive portal — a frontend prototype built on Django.
Agents see their point balance, tier standing, a live leaderboard, a weekly
trend, a monthly video briefing, and a policy assistant.

**Everything is mock.** There is no database-backed model, no auth, and no LLM.

## Setup

```bash
python3 -m venv .venv
.venv/bin/pip install django
.venv/bin/python manage.py runserver
```

Then open <http://127.0.0.1:8000/>.

No migrations are needed — the project defines no models. The `db.sqlite3` file
is unused; Django's built-in apps are installed but nothing here reads them.

## Routes

| Path | Name | View |
|---|---|---|
| `/` | `landing` | Marketing page: tier explorer + avatar guide |
| `/dashboard/` | `dashboard` | Field agent dashboard |
| `/faqs/` | `faqs` | FAQ accordion, sourced from `chat_responses.py` |
| `/login/` | `login` | Sign-in form (GET) and credential check (POST) |
| `/logout/` | `logout` | POST-only sign out; a stray GET redirects |
| `/profile/` | `profile` | Account profile, editable phone and location |
| `/notifications/` | `notification_settings` | Autosaving notification preferences |
| `/api/chat/` | `chat_api` | `POST` JSON endpoint for the policy assistant |

`/dashboard/`, `/profile/` and `/notifications/` are wrapped in `agent_required`.
`/`, `/faqs/` and `/login/` are public.

## Structure

```
spectrum_portal/          Django project config
dashboard/
  mock_data.py            ← single source of truth for every number
  chat_responses.py       ← canned policy answers, keyword matched
  context_processors.py   ← shares auth flag + agent identity with every page
  decorators.py           ← agent_required, session-only access control
  views.py                landing, agent_dashboard, faqs, auth_toggle, chat_api
  urls.py
  templates/dashboard/
    base.html             navbar, footer, skip link, blocks
    landing.html
    dashboard.html
    faqs.html
    login.html
    account_base.html       shared Account shell + tab strip
    profile.html
    notifications.html
    partials/
      _chat_widget.html       (markup + the single sendMessage path)
      _avatar_explainer.html  (markup + chapter script; landing page only)
  static/dashboard/
    css/spectrum.css      design system + all component styles
    js/ui.js              window.SP — reveal observer, animateCount, toast
    img/spectrum-logo.svg   official mark, committed locally
    img/favicon.ico         downloaded once, served locally
    img/briefing-poster.svg
```

### `mock_data.py` — the single source of truth

No point value or threshold is hardcoded anywhere else in the project. It holds
`TIERS` (Bronze 0–2499, Silver 2500–4999, Gold 5000+), `CURRENT_AGENT`,
`LEADERBOARD`, `KPI_STATS`, `WEEKLY_POINTS`, and `HEADLINE_STAT`, plus
`get_tier(points)` and `points_to_next_tier(points)` — which returns `None` at
the top tier so callers must handle Gold explicitly.

Everything is shaped like a JSON API response (plain dicts and lists), so each
constant can be swapped for a real endpoint payload without touching a template.

Run its self-check directly:

```bash
.venv/bin/python dashboard/mock_data.py     # prints "mock_data OK"
```

### `chat_responses.py` — the chatbot is a keyword stub

**There is no model call.** `match_question(text)` lowercases the input and
returns the first entry whose keywords appear as a substring, else
`FALLBACK_RESPONSE`. Six topics are covered: how points are calculated, payout
timing, Gold requirements, expiry, leaderboard ranking, and qualified upsells.

Every figure in every answer is interpolated from `mock_data`, so the assistant
can never state a number that contradicts the dashboard. Its self-check asserts
each pill round-trips to its own answer:

```bash
.venv/bin/python -c "import os,django,runpy; \
  os.environ.setdefault('DJANGO_SETTINGS_MODULE','spectrum_portal.settings'); \
  django.setup(); runpy.run_module('dashboard.chat_responses', run_name='__main__')"
```

## Brand

### Palette

The official Spectrum values, defined as custom properties in `spectrum.css`:

| Token | Value | Use |
|---|---|---|
| `--sp-blue` | `#005EFF` | primary — CTAs, active states, key emphasis |
| `--sp-blue-hover` | `#0171EB` | accent, hover, links |
| `--sp-navy` | `#00194A` | headings, wordmark, avatar, dark surfaces |
| `--sp-white` | `#FFFFFF` | surfaces |
| `--sp-bg` | `#F5F7FA` | page background |
| `--sp-text` | `#212121` | body copy |
| `--sp-muted` | `#5A6472` | secondary text |
| `--sp-border` | `#E1E6ED` | hairlines |
| `--sp-error` | `#B42318` | form validation only — the one warranted red |

Bootstrap's `--bs-primary` and `--bs-link-color` are overridden to `--sp-blue`.

**Tier metallics** are the only additional hues in the product, which is what
keeps them meaningful:

| Tier | Solid | Background |
|---|---|---|
| Bronze | `#B0703C` | `#FBF1E9` |
| Silver | `#7A8794` | `#F2F4F7` |
| Gold | `#C8992A` | `#FDF6E3` |

Tier badges pair the metallic with a 1px/2px/3px border-weight progression, so
rank still reads in greyscale and for colorblind users. Tier colour appears on
five surfaces: the leaderboard column, the Points & Tier badge, the progress bar
fill, the tier explorer tabs and indicator, and the explorer's detail panel. The
current agent's row highlight stays `--sp-blue` — that marks *identity*, not
tier, and the two must not be confused.

Buttons are fully rounded pills (`.btn-sp-primary`, `.btn-sp-secondary`), and
cards, panels, inputs and the chat window use a 16px radius.

### Typography

Spectrum Sans is proprietary and not on any CDN. `--sp-font` names it first and
falls back to **Inter**, loaded from Google Fonts at weights 400/500/600/700:

```css
--sp-font: "Spectrum Sans", "Inter", -apple-system, ...;
```

Licensing the real font later is a drop-in — no selector changes, just make the
family resolve. The type scale is 32 / 20 / 15 / 13px on a 16px body.

### Logo

`dashboard/static/dashboard/img/spectrum-logo.svg` was downloaded once from
Spectrum's buyflow CDN and is committed locally — it is served with `{% static %}`
and never hotlinked at runtime. The navbar pairs it with a 1px divider and
"Incentive Portal" in `--sp-muted`, so the portal reads as a sub-brand.

**One edit to the official asset:** its navy was `#032139`; it is mapped to
`#00194A` so the mark matches the brand navy used beside it. Re-download the
file to restore the byte-exact original.

The favicon was downloaded from `official.spectrum.com` and is also served
locally.

## Navbar

Signed **in**, the navbar shows a profile dropdown (initials avatar, first name,
caret) hand-rolled in vanilla JS — not Bootstrap's dropdown — closing on outside
click, Escape and focus leaving the menu, with arrow-key navigation. Its links go
to `/profile/` and `/notifications/`, and Sign Out is a CSRF-protected POST form,
not a link. Signed **out**, a single "Sign in" pill replaces it. The login page
hides the nav links and profile menu entirely, showing only the logo lockup.

## Auth — prototype only

> **This is not real authentication.** Credentials are hardcoded constants
> compared in plain text, there is no user store, no password hashing, no rate
> limiting and no lockout. It exists so a reviewer can see the signed-in and
> signed-out states. **Replace it with a real auth backend before any non-demo
> use, and never deploy it as-is.**

### Demo credentials

```
Email:    agent@spectrum.com
Password: spectrum2026
```

They are defined in `mock_data.py` (`DEMO_EMAIL` / `DEMO_PASSWORD`) and shown in
a dashed "Demo access" box on the login page so a grader can get in.

### How it works

No Django auth app, no user model, no migrations. `login` compares the
submitted email (stripped, case-insensitive) and password against the constants
and sets `request.session["is_authenticated"]`. `logout` is POST-only with CSRF
and flushes the session. Sessions use the signed-cookie backend, so none of this
needs a database table.

`dashboard/decorators.py` holds `agent_required`, which redirects signed-out
visitors to `/login/?next=<path>` — no Django auth imports. The `next` value is
only honoured when it is a relative in-site path, so an external URL can never
be used as a redirect target.

Failed sign-in returns one non-specific message — "The email or password you
entered is incorrect." — regardless of which field was wrong, and the submitted
email is preserved while the password never is.

`dashboard/context_processors.py` exposes `is_authenticated` and `current_agent`
to every template, so the navbar, the landing CTAs and the account pages all read
the same state.

## Account pages

Both sit under `account_base.html`, which supplies the "Account" heading and a
tab strip. The tabs are real links to real routes, not JS tabs, so each survives
a refresh and deep-links cleanly.

**My Profile** shows an identity card (72px initials avatar, name, job title,
tier badge), a two-column details list, and a performance summary pulled from the
`mock_data` helpers. Only **phone** and **location** are editable: "Edit details"
swaps those two values for inputs in place, Save POSTs them into the session, and
Cancel restores from a `data-original` attribute with no round trip. Everything
else is marked managed by HR.

**Notifications** renders nine preferences across three groups, each with Email
and Push switches hand-rolled from a checkbox plus a styled track — no Bootstrap
switch, no library, keyboard operable with a visible focus ring. Every change
autosaves to the session (debounced 300ms per key+channel) and flashes "Saved".
A digest frequency segmented control and a master mute switch save the same way;
mute dims and disables the toggles **without** clearing what is stored, so
switching it back off restores exactly what was set. Preferences read from the
session with the `mock_data` defaults as fallback.

## Interactive features

- **Tier explorer** (landing) — ARIA tablist, 200ms panel crossfade, sliding 2px
  indicator, arrow/Home/End key navigation
- **Hero entrance** — headline words fade and rise in sequence via CSS
  `transition-delay`
- **Reveal on scroll** — one shared `IntersectionObserver` staggers `.u-reveal`
  elements by 60ms
- **Count-up numbers** — `SP.animateCount` with an ease-out curve, used by the
  KPI cards, the balance, and the landing headline stat
- **Leaderboard** — sortable on all five columns with a caret that rotates 180°,
  120ms debounced text filter, multi-select region chips, expandable detail rows
  (one at a time), and a live "Showing X of N" count. The current agent's row
  keeps its blue left border and tint through every sort and filter.
- **Tier progress bar** — animates 0 → its width over 900ms; Gold shows
  "Top tier reached" instead of a bar
- **Sparkline** — inline SVG polyline, no library, hover/focus tooltips
- **Policy assistant** — expanding launcher, sliding panel, typing indicator,
  FAQ pills looped from `FAQ_RESPONSES` in the template. The widget partial
  carries its own script and exposes `window.SPChat`, so the FAQ page drives the
  same `sendMessage` path rather than duplicating it.
- **FAQ page** — live search across question *and* answer text (120ms debounce),
  hand-rolled accordion with height transition and a rotating chevron, multiple
  panels open at once, and an "Ask the assistant" button per answer that opens
  the chat with that question already sent
- **Avatar guide** — on the **landing page**, beside the hero copy (6/6,
  vertically centred, stacking under 992px). Video container, local SVG poster
  and play overlay only; the chapter list was removed.
- **Login** — show/hide password toggle, on-blur inline validation, submitting
  state with a CSS spinner
- **Account** — in-place profile editing, hand-rolled notification switches,
  segmented digest control, master mute

### Accessibility

Skip-to-content link, visible `:focus-visible` rings throughout, full keyboard
paths (nav → tier explorer → leaderboard sort/filter/expand → chat), ARIA roles
on the tablist, table sort headers, expandable rows, and the chat log.
`prefers-reduced-motion` disables transitions, stagger delays, and count-up
animation — values jump straight to their final state.

Tiers are distinguished by typography and border weight, never color. Deltas use
▲/▼ glyphs and font weight, never red/green.

## Adding a real avatar video

`partials/_avatar_explainer.html` — included on the **landing page**, not the
dashboard — has a commented block marking where the `<source>` or provider
`<iframe>` goes. The play overlay already drives the element, so it works
unchanged the moment a source is added.

## Next: Manager and Director roles

The current build serves one persona — the field agent. The next slice adds:

- **Manager** — team roster view, per-agent drill-down, tier distribution across
  a team, and the ability to flag a job for quality review. Needs
  `mock_data` to grow a `TEAMS` structure and agents to carry a `manager_id`.
- **Director** — region-level rollups, cost-of-program against payout budget,
  and tier migration over time. Mostly aggregation over the same shapes.
- **Shared work** — a role switcher, per-role nav, and moving the leaderboard's
  sort and filter server-side once the board outgrows a single page.
