# Spectrum Incentive Portal

An internal incentive-programme portal for Spectrum field operations, built as a
working frontend prototype on Django.

**Live demo — [spectrum-incentive-portal.vercel.app](https://spectrum-incentive-portal.vercel.app/)**

Field technicians log their work and watch points, tier and standing update.
Managers review those submissions and author incentive programmes. Directors
compare competing programmes, weigh them against budget, and approve them. The
loop closes: a director approves a programme and the technician sees it on their
dashboard the same day.

> **This is a prototype.** There is no database, no real authentication, and no
> language model. Every one of those is a deliberate, documented choice — see
> [Prototype boundaries](#prototype-boundaries). Nothing here is production-ready
> and nothing pretends to be.

---

## Contents

- [Quick start](#quick-start)
- [Demo accounts](#demo-accounts)
- [Guided walkthrough](#guided-walkthrough)
- [What each role can do](#what-each-role-can-do)
- [Architecture](#architecture)
- [How the data holds together](#how-the-data-holds-together)
- [Engineering notes](#engineering-notes)
- [Design system](#design-system)
- [Accessibility](#accessibility)
- [Deployment](#deployment)
- [Prototype boundaries](#prototype-boundaries)
- [Roadmap](#roadmap)

---

## Quick start

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python manage.py runserver
```

Open <http://127.0.0.1:8000/>.

No migrations are needed — the project defines no models and uses signed-cookie
sessions. `db.sqlite3`, if present, is unused.

Run the data self-checks at any time:

```bash
.venv/bin/python dashboard/mock_data.py        # derivations and archetypes
.venv/bin/python -c "import os,django,runpy; \
  os.environ.setdefault('DJANGO_SETTINGS_MODULE','spectrum_portal.settings'); \
  django.setup(); runpy.run_module('dashboard.store', run_name='__main__')"
```

## Demo accounts

Password for all three: **`spectrum2026`**

| Role | Email | Person | Lands on |
|---|---|---|---|
| Agent | `agent@spectrum.com` | Dana Whitfield — Field Installation Technician | `/dashboard/` |
| Manager | `manager@spectrum.com` | Marcus Vale — Field Operations Manager | `/manager/` |
| Director | `director@spectrum.com` | Priya Raghunathan — Director of Field Operations | `/director/` |

The login page has a role picker that fills the form in one click.

## Guided walkthrough

The portal is built around one workflow crossing three people. Use three browser
sessions (one normal, two incognito) so all three roles are signed in at once.

| | Who | Do this |
|---|---|---|
| 1 | **Dana** | Open **Log Work**. Add three jobs, toggling modifiers and watching the live points preview. **Submit day for approval**. |
| 2 | **Marcus** | Open **Approvals** — the navbar badge has updated. Approve two entries; on the third choose **Request changes** and write a reason. The submit button stays disabled until you do. |
| 3 | **Dana** | Approved points move from *pending* to the banked ledger figure. The third entry shows Marcus's note and is editable again. Fix and resubmit. |
| 4 | **Marcus** | **Programs → Create programme**. The preview pane mirrors what the director will see; the budget computes from participants × bonus points × point rate. Submit for approval. |
| 5 | **Priya** | **Programs** — select up to three proposals to compare side by side, most favourable value highlighted per row. **Approvals** shows budget impact and flags any approved programme overlapping the same dates and job types. Approve with a note. |
| 6 | **Marcus / Dana** | Marcus sees the new status. Dana sees the programme under **Active programmes**, with the bonus rule in plain language. |

Reset the demo state between runs (local only):

```bash
curl -X POST http://127.0.0.1:8000/dev/reset-store/
```

> Run a **single worker**. Shared state lives in process memory, so multiple
> workers means the three roles see different worlds. `runserver` is
> single-process, which is what this demo needs.

## What each role can do

### Field agent

- **Dashboard** — four KPI tiles, points-and-tier card with animated progress,
  a dollar ledger separating banked from pending, an eight-week sparkline, and a
  what-if simulator projecting tier crossover from extra work.
- **Log Work** — record jobs against nine job types and five modifiers, with a
  live points preview that recalculates on every change. Submit the day for
  approval; drafts stay editable, submitted entries lock.
- **AI Insights** — personalised prompts generated from the agent's own activity
  (rule-based, not a model — see [Prototype boundaries](#prototype-boundaries)).
- **FAQs and Policy Assistant** — programme rules answered without asking anyone.

### Manager

- **Team** — six KPIs, a sortable 18-technician roster with inline data bars,
  filter chips and per-agent drill-down, plus a twelve-week team trend.
- **Burnout watch** — flags technicians on overtime, consecutive days worked, or
  a repeat rate well above team average. Deliberately restrained: a coaching
  prompt, not an alarm, with the triggering rule stated on the card.
- **Approvals** — a two-pane review queue grouped by technician and day.
  Rejecting or requesting changes **requires a note**.
- **Programs** — a three-section authoring form with a live preview showing
  exactly what the director will review.

### Director

- **Overview** — territory KPIs, a manager comparison table, and an ROI tracker
  attributing modelled savings to reduced repeat visits, lower turnover and
  improved first-time fix.
- **Programs** — up to three proposals side by side, with the most favourable
  value marked per attribute and a "show only differences" filter.
- **Approvals** — budget impact against the quarter and a conflict check for
  approved programmes overlapping in both dates and job types.

---

## Architecture

Django 6.1, server-rendered templates, vanilla JavaScript. Bootstrap 5 supplies
the grid and a small amount of base CSS; everything else is a purpose-built
design system. No frontend framework, no build step for the client.

```
spectrum_portal/          project configuration
dashboard/
  mock_data.py            seeded reference data + all derived figures
  store.py                mutable runtime state (work logs, programmes)
  insights.py             rule-based insight engine
  chat_responses.py       keyword-matched policy answers
  decorators.py           role_required — session-only access control
  context_processors.py   auth state and role-aware navigation
  views.py                all views for all three roles
  templates/dashboard/    page templates + partials/
  static/dashboard/       css/, js/, img/
staticfiles/              collected output, committed for deployment
```

### Routes

| Path | Name | Access |
|---|---|---|
| `/` | `landing` | public |
| `/login/`, `/logout/` | `login`, `logout` | public |
| `/faqs/` | `faqs` | public |
| `/dashboard/` | `dashboard` | agent |
| `/log-work/` | `log_work` | agent |
| `/manager/`, `/manager/programs/`, `/manager/approvals/` | — | manager |
| `/director/`, `/director/programs/`, `/director/approvals/` | — | director |
| `/profile/`, `/notifications/` | — | any signed-in role |
| `/api/chat/` | `chat_api` | public (serves the FAQ page) |

`role_required(*roles)` sends signed-out visitors to `/login/?next=…` and renders
a styled 403 inside the portal chrome — never a bare Django error — when a
signed-in user reaches an area their role does not cover. `?next=` is honoured
only when the path is relative, in-site, **and** permitted for that role.

---

## How the data holds together

Every figure is either **seeded ground truth** or **derived from it**. Nothing is
typed twice, so no two cards can contradict each other.

**Seeded:** tier thresholds, job base points, modifiers, `POINT_VALUE_USD`, the
five archetypes and each agent's assignment, and prior-period actuals so a
"vs last month" delta has something real to be a delta *of*.

**Derived at import:** points balance is the sum of approved entry points; rank
is position after sorting by points; tier is `get_tier(points)`; the sparkline is
those same entries bucketed by week; team and territory totals are sums over
their members; a programme's budget is participants × bonus points × point rate.

### Two levels of truth

Dana and the five technicians whose logs the manager queue needs carry
**entry-level** history — every point traces to a logged job. The other twelve
carry **aggregate** monthly totals from their archetype, because seeding hundreds
of entries for agents nobody drills into would be noise. Both sit on one scale:
daily job volume is computed *from* the archetype's monthly target.

### Archetypes

The roster is generated from five kinds of technician so metrics correlate the
way real field-service metrics do — rushing causes callbacks, tenure builds skill.

| Archetype | Reads as |
|---|---|
| Veteran high performer | long tenure, low repeat rate, Gold tier |
| Steady mid-tier | the Silver bulk of the team |
| Fast but sloppy | high volume and overtime, so more callbacks and lower CSAT |
| New hire ramping | under six months, Bronze, more callbacks, fewer audits passed |
| Burnout risk | the only technicians over the overtime line — exactly who the burnout watch flags |

The self-check enforces these: no Gold technician may carry a high repeat rate,
nobody under six months may be above Bronze, and only the burnout archetype may
breach the overtime threshold.

---

## Engineering notes

### One point calculation, two implementations that cannot drift

`mock_data.calculate_points(job_type, modifiers)` is the single source of truth.
The browser mirrors it from `JOB_TYPES` and `POINT_MODIFIERS` handed over as JSON
in a data attribute — nothing is hardcoded twice.

One subtlety: Python's `round()` rounds halves to even while JavaScript's
`Math.round` goes half-up, so `90 × 0.15 = 13.5` would have diverged. The server
uses `floor(x + 0.5)` to match. All **288** job × modifier combinations were
compared between the two implementations and agree exactly.

The server always recalculates on write — a points value in a POST body is
ignored.

### An unexplained decision is impossible

Rejecting a work log or a programme, or requesting changes, **requires a note**.
This is enforced in `store.review_batch()` and `store.review_program()`, not just
by a disabled button, so it holds against a crafted request. A rejection with no
reason is exactly the opacity this portal exists to remove.

### Approved-only daily totals

`store.get_day_summary()` is the single source for a day's figures, and only
**approved** entries count — the same "not banked yet" rule the ledger uses. A day
holding only drafts reports zeroes with a caption explaining why, so the zeroes
are never mistaken for "nothing happened".

### Modelled versus measured

The director's ROI tracker states plainly that its figures are **modelled
estimates on demo assumptions**, and exposes every assumption with its source
note. Presenting a modelled number as measured fact is the failure this guards
against, so the distinction is visible rather than buried.

---

## Design system

Two hues carry the entire product: one Spectrum blue and a neutral ramp.

| Token | Value | Use |
|---|---|---|
| `--sp-blue` | `#005EFF` | primary — CTAs, active states, emphasis |
| `--sp-blue-hover` | `#0171EB` | hover, links |
| `--sp-navy` | `#00194A` | headings, wordmark, avatars |
| `--sp-bg` | `#F5F7FA` | page background |
| `--sp-text` | `#212121` | body copy |
| `--sp-muted` | `#5A6472` | secondary text |
| `--sp-border` | `#E1E6ED` | hairlines |
| `--sp-error` | `#B42318` | validation and rejected state |
| `--sp-warning` | `#B25E09` | changes-requested and the safety flag |
| `--sp-earned` | `#1E7E34` | the single green — the live earnings tile only |

**Tier colours** are the only additional hues, and they are derived rather than
picked — all three sit at one lightness (HSL L 34%) with chroma ascending, so
they read as one family with a legible hierarchy:

| Tier | Solid | Tint | vs white | vs own tint |
|---|---|---|---|---|
| Bronze | `#7F472F` | `#F9F1EE` | 7.42:1 | 6.62:1 |
| Silver | `#3E4B6F` | `#F0F2F7` | 8.56:1 | 7.68:1 |
| Gold | `#806E2D` | `#F9F7EE` | 5.00:1 | 4.67:1 |

The warm tones are cool-shifted and desaturated so they sit beside `#005EFF`
without looking imported; silver is held a measured distance from `--sp-muted`
so a badge never reads as disabled text, and far from `--sp-blue` so it never
reads as a primary element. Badges pair the colour with a 1px/2px/3px
border-weight progression, which matters more now the hues sit closer together —
it keeps rank readable in greyscale and for colourblind readers.

Deltas use ▲/▼ glyphs and font weight, never red and green. Buttons are fully
rounded pills; cards, panels, inputs and modals share a 16px radius.

**Typography** — Spectrum Sans is proprietary, so `--sp-font` names it first and
falls back to Inter. Licensing the real face later is a drop-in. Scale is
32 / 20 / 15 / 13px on a 16px body.

**Logo** — the official mark is committed locally and served with `{% static %}`,
never hotlinked. Its navy was remapped to `#00194A` so the lockup matches the
navbar; re-download the file to restore the byte-exact original.

## Accessibility

Skip-to-content link, visible `:focus-visible` rings throughout, and full
keyboard paths across navigation, the tier explorer, the leaderboard's
sort/filter/expand, the entry form, and the chat widget. ARIA roles on the
tablist, sortable table headers, expandable rows, switches, progress bars and the
chat log. `prefers-reduced-motion` disables transitions, stagger delays and
count-up animation, sending values straight to their final state.

---

## Deployment

The live demo runs on Vercel. On that platform only **one** environment variable
is required — the app reads Vercel's own `VERCEL`, `VERCEL_URL` and
`VERCEL_PROJECT_PRODUCTION_URL` to switch debug off and populate
`ALLOWED_HOSTS` and `CSRF_TRUSTED_ORIGINS` automatically.

| Variable | Required | Notes |
|---|---|---|
| `DJANGO_SECRET_KEY` | **yes** | The app refuses to boot without it in a deployed environment — the committed fallback key is public, so cookies signed with it can be forged |
| `DJANGO_DEBUG` | no on Vercel | Auto-`False` when `VERCEL` is present |
| `DJANGO_ALLOWED_HOSTS` | no on Vercel | Comma-separated, for hosts that do not advertise themselves |
| `CSRF_TRUSTED_ORIGINS` | no on Vercel | Scheme-qualified, e.g. `https://portal.example.com` |
| `ENABLE_DEV_TOOLS` | no | Defaults to `DEBUG`; gates the unauthenticated reset route |

```bash
python -c "from django.core.management.utils import get_random_secret_key as k; print(k())"
```

> Vercel injects environment variables at deployment time. Adding one to a
> running deployment has no effect until you redeploy.

**Project settings:** Framework Preset **Other**, Root Directory `./`, and leave
Build Command, Output Directory and Install Command **empty** — `vercel.json`
uses the `builds` key, which makes Vercel ignore those fields entirely.

**No build step, and no `migrate`.** `staticfiles/` is committed deliberately:
`collectstatic` never runs on Vercel, and with a manifest storage backend a
missing manifest is not graceful degradation but `ValueError` on every page.
Committing the output removes that failure mode — WhiteNoise serves the files
from inside the lambda with gzip and immutable cache headers.

Re-run this after changing anything under `dashboard/static/`, or the deployed
site serves stale assets:

```bash
python manage.py collectstatic --noinput --clear
```

`django.contrib.admin` is removed from `INSTALLED_APPS`: it was never routed, and
its assets were 5.1MB of a 5.3MB payload against a 15MB lambda limit.

---

## Prototype boundaries

Four things are deliberately not real. Each is isolated behind a seam so it can
be replaced without touching the interface.

### State is process memory, not a database

`store.py` is a module-level singleton holding work logs and programmes. Session
storage cannot carry a workflow between two people — when an agent submits a log,
a manager in a different browser has to see it — and this is what makes that
possible without a database.

**It is not persistent.** A restart wipes it, and it does not survive multiple
processes or serverless instances. On the Vercel demo, **reads are consistent**
(the seed is deterministic, so every instance derives identical data) but
**writes may not persist** between requests. For a fully working round trip, run
locally or on a single-container host such as Render or Railway — no code changes
needed. The real fix is Django models and a database.

Views never touch `STORE` directly; every read and write goes through a helper
holding a `threading.Lock`, and reads return deep copies.

### Authentication is a credential comparison

There is no auth app, no user model, no password hashing, no rate limiting.
`login` compares the submitted email and password against constants and sets a
session flag. It exists so a reviewer can see all three roles. **Replace it with
a real backend before any non-demo use.**

Access control, however, is real: enforced server-side by `role_required`, with
ownership checks inside the store rather than the view, so an agent cannot edit
another agent's entry by crafting a request.

### The assistant matches keywords

`chat_responses.py` has no model call. `match_question()` lowercases the input and
returns the first entry whose keywords appear as a substring. Six shared topics
plus one each for managers and directors. Every figure in every answer is
interpolated from `mock_data`, so the assistant cannot state a number that
contradicts the dashboard.

### AI Insights is a rule engine

`insights.py` evaluates six fixed conditions against the agent's own logged work
and returns the top four that fire. No model, no inference. The card footer says
"Generated from your recent activity", which is exactly what happens.

---

## Roadmap

- **Persistence** — replace `store.py` with Django models and a managed database,
  which also makes the portal correct on serverless hosting.
- **Real authentication** — a proper backend, SSO against the corporate directory,
  and role claims from HR rather than a constant.
- **Live data** — swap `mock_data` for the work-order and CSAT systems. Every
  constant is already shaped like an API response for this reason.
- **A real avatar briefing** — `partials/_avatar_explainer.html` marks the
  drop-in point.
- **Notifications that send** — the preference UI is complete; nothing dispatches.

---

*Internal prototype. Not affiliated with or endorsed by Charter Communications.*
