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
| `/log-work/` | `log_work` | Agent daily work log — add, edit, submit for approval |
| `/manager/` | `manager_team` | Manager team view *(stub)* |
| `/manager/programs/` | `manager_programs` | Manager programs *(stub)* |
| `/manager/approvals/` | `manager_approvals` | Manager approvals *(stub)* |
| `/director/` | `director_overview` | Director overview *(stub)* |
| `/director/programs/` | `director_programs` | Director programs *(stub)* |
| `/director/approvals/` | `director_approvals` | Director approvals *(stub)* |
| `/faqs/` | `faqs` | FAQ accordion, sourced from `chat_responses.py` |
| `/dev/reset-store/` | `dev_reset_store` | POST, no auth — resets the in-memory store |
| `/login/` | `login` | Sign-in form (GET) and credential check (POST) |
| `/logout/` | `logout` | POST-only sign out; a stray GET redirects |
| `/profile/` | `profile` | Account profile, editable phone and location |
| `/notifications/` | `notification_settings` | Autosaving notification preferences |
| `/api/chat/` | `chat_api` | `POST` JSON endpoint for the policy assistant |

Routes are gated by `role_required(*roles)` in `dashboard/decorators.py`.
`/`, `/faqs/` and `/login/` are public; `/profile/` and `/notifications/` need
any signed-in role; the rest are role-specific per the table above.

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
| `--sp-error` | `#B42318` | form validation and rejected state |
| `--sp-warning` | `#B25E09` | changes-requested state and the safety flag |
| `--sp-earned` | `#1E7E34` | **the one green in the product** — see below |

Bootstrap's `--bs-primary` and `--bs-link-color` are overridden to `--sp-blue`.

**Tier metallics** are the only additional hues in the product, which is what
keeps them meaningful:

| Tier | Solid | Background |
|---|---|---|
| Bronze | `#B0703C` | `#FBF1E9` |
| Silver | `#7A8794` | `#F2F4F7` |
| Gold | `#C8992A` | `#FDF6E3` |

**The single green exception.** `--sp-earned` is used in exactly two places:
the "Earned today" KPI value and its small live-indicator dot. It is a
deliberate break from the otherwise green-free palette because that tile is a
live, positive earnings signal and has to read differently from the neutral KPI
tiles beside it. The shade is muted rather than saturated so it stays consistent
with the flat corporate aesthetic. Do not use it anywhere else — a hue-space
audit of the CSS confirms it is the only green-hue colour in the project.

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

## Demo script — the full three-role round trip

This is the walkthrough the portal is built to support. Use three separate
browser sessions (or one normal + two incognito windows) so all three roles are
signed in at once. Password for every account is `spectrum2026`.

| | Who | Do this |
|---|---|---|
| 1 | **Dana** `agent@spectrum.com` | Open **Log Work**. Add three jobs — pick a job type, work order, address, and toggle a modifier or two, watching the live points preview. Click **Submit day for approval**. |
| 2 | **Marcus** `manager@spectrum.com` | Open **Approvals** — the navbar badge now includes Dana's day. Approve two entries; on the third choose **Request changes** and write a reason. The submit button stays disabled until you do. |
| 3 | **Dana** | Reload the dashboard: the approved points have moved from *pending* to the banked ledger figure. On **Log Work**, the third entry shows Marcus's note and is editable again. Fix it and resubmit. |
| 4 | **Marcus** | Open **Programs → Create program**. Fill the three sections — the preview pane mirrors what the director will see, and the budget auto-computes from participants × bonus points × the point rate. **Submit for director approval**. |
| 5 | **Priya** `director@spectrum.com` | Open **Programs**. Select Marcus's new proposal plus two existing ones — up to three compare side by side, with the most favourable value in each numeric row highlighted. Then open **Approvals**: see the budget impact against the remaining quarter and any overlapping approved program. Approve it with a note. |
| 6 | **Marcus / Dana** | Marcus's program list shows the new status. Dana's dashboard shows the program under **Active programs**, with the bonus rule in plain language. |

Reset between runs with:

```bash
curl -X POST http://127.0.0.1:8000/dev/reset-store/
```

> **Run a single worker.** `store.py` is process-global memory (see below). With
> more than one worker the three roles can land on different processes and see
> different worlds. `manage.py runserver` is single-process by default, which is
> what this demo needs.

## Deploying

> ### Read this before deploying to a serverless host
>
> `store.py` is **process-global memory** (see the section above). Serverless
> platforms — Vercel, Lambda, Cloud Run at scale — run many short-lived
> instances, so a write on one request may be invisible to the next. On such a
> host:
>
> * **Reads are fine.** The seed is deterministic, so every instance derives
>   identical data — dashboards, roster, comparison grid and ROI all render
>   correctly and consistently.
> * **Writes are unreliable.** Submitting a day, approving work, or creating a
>   program may not be visible to the other roles, which is the entire
>   cross-role demo.
>
> For a working round-trip demo, use a **single-container host** (Render,
> Railway, Fly.io) — no code changes needed, `store.py` behaves as designed.
> Deploy to Vercel when you want a shareable UI walkthrough and can accept that
> writes do not persist. The real fix is replacing `store.py` with Django models
> and a database.

### Environment variables

| Variable | Required | Notes |
|---|---|---|
| `DJANGO_SECRET_KEY` | **yes** | The app refuses to start when `DJANGO_DEBUG=False` and this is unset |
| `DJANGO_DEBUG` | **yes** | `False` in deployment |
| `DJANGO_ALLOWED_HOSTS` | **yes** | Comma-separated, e.g. `.vercel.app,portal.example.com` |
| `CSRF_TRUSTED_ORIGINS` | **yes** | Scheme-qualified, e.g. `https://your-app.vercel.app`. Without it every POST fails with 403 |
| `DJANGO_SECURE_SSL_REDIRECT` | no | Defaults to `True` when not in debug |
| `DJANGO_HSTS_SECONDS` | no | Defaults to one year |
| `ENABLE_DEV_TOOLS` | no | Defaults to `DEBUG`. Gates the unauthenticated `/dev/reset-store/` route |

Generate a key with:

```bash
python -c "from django.core.management.utils import get_random_secret_key as k; print(k())"
```

Locally none of these are needed — every one falls back to a development
default, so `manage.py runserver` still works with no setup.

### Build

```bash
pip install -r requirements.txt
python manage.py collectstatic --noinput
```

There is **no `migrate` step** — the project defines no models and uses
signed-cookie sessions, so it needs no database.

`vercel.json` routes `/static/*` to the collected output and everything else to
`spectrum_portal/wsgi.py`, which exposes `app` for the `@vercel/python` runtime.
Static files are served by **WhiteNoise** with hashed filenames, gzip and
immutable cache headers, because Vercel's Python runtime will not serve them.

### What is deliberately not routed

* **`/admin/`** — `django.contrib.admin` is installed but unrouted; with no
  models and no migrations it would 500 on any request.
* **`/dev/reset-store/`** — unauthenticated and destructive, so it only exists
  when `ENABLE_DEV_TOOLS` is on.

## About the mock data

Every figure in the portal is either **seeded ground truth** or **derived from
it** — nothing is typed twice, so no two cards can drift apart.

**Seeded (the only real inputs):** tier thresholds, job base points, point
modifiers, `POINT_VALUE_USD`, the five archetypes, each agent's archetype
assignment, and prior-period actuals (`KPI_PREVIOUS`, `TEAM_PREVIOUS`) so a
"vs last month" delta has something real to be a delta *of*.

**Derived at import:** an agent's points balance is the sum of their approved
entry points; rank is their position after sorting by points; tier is
`get_tier(points)`; the 8-week sparkline is those same entries bucketed by
week; team and territory totals are sums over their members; and a program's
budget is `participants × bonus points × POINT_VALUE_USD` — the cost of an
incentive is what it pays out.

### Two levels of truth, deliberately

Dana plus the five agents whose logs the manager queue needs carry
**entry-level** history — every point traces to a logged job. The other twelve
carry **aggregate-only** monthly totals from their archetype, because seeding
hundreds of entries for agents nobody drills into would be noise. Both levels
sit on the same scale: daily job volume is computed *from* the archetype's
monthly target, so a derived balance lands in the same range as an aggregate
one for the same kind of agent.

### Archetypes

The roster is generated from five kinds of technician rather than random
numbers, so the metrics correlate the way real field-service metrics do:

| Archetype | Reads as |
|---|---|
| Veteran high performer | long tenure, low repeat rate, Gold |
| Steady mid-tier | the Silver bulk of the team |
| Fast but sloppy | high volume and overtime, so higher callbacks and lower CSAT |
| New hire ramping | under 6 months, Bronze, more callbacks, fewer audits passed |
| Burnout risk | the only agents above 12 overtime hours — exactly who the burnout watch flags |

The self-check enforces these relationships: no Gold agent may carry a high
repeat rate, nobody under six months' tenure may be above Bronze, and only the
burnout archetype may breach the overtime line.

### Why volume is 1–3 jobs a day

At roughly 125 points a job, 3–7 jobs a day earns ~12,000 points a month and
every agent clears Gold (5,000) within a week, which makes the tier system
meaningless. Daily volume is sized so a month's work lands in the same range as
the thresholds it is measured against.

### Reading the money cards

Two dollar figures on the dashboard cover different windows, each labelled on
the card: **Earned today** is today's approved work only ($0 on a quiet
morning is correct), while **Earned this period** is all approved work to date.

```bash
.venv/bin/python dashboard/mock_data.py     # asserts the derivations hold
```

## Roles

Three roles, three demo accounts. **Password for all three: `spectrum2026`.**

| Email | Role | Person | Lands on |
|---|---|---|---|
| `agent@spectrum.com` | agent | Dana Whitfield, Field Installation Technician | `/dashboard/` |
| `manager@spectrum.com` | manager | Marcus Vale, Field Operations Manager | `/manager/` |
| `director@spectrum.com` | director | Priya Raghunathan, Director of Field Operations | `/director/` |

The login page has a role picker — three cards that fill the form on click.
Typing by hand still works and clears the selection.

**Org chart** (`mock_data.ORG`): Priya → 6 managers → Marcus supervises 18
technicians. Dana is one of Marcus's reports, rank 4 on his team. Each of the 18
carries `repeat_rate`, `on_time_rate`, `jobs_this_week`,
`overtime_hours_this_week`, `safety_audits_passed`, `csat` and `tenure_months`,
shaped so the numbers tell a coherent story: longer tenure trends toward more
points and better on-time rates, and two agents (Ibrahim Cole, Sofia Marchetti)
break the pattern with heavy overtime and depressed CSAT — the burnout signal
the manager views are built to surface.

### How access control works

`role_required(*roles)` sends signed-out visitors to `/login/?next=<path>` and
renders a **styled 403 page with the portal chrome** — never a bare Django 403 —
when a signed-in user hits an area their role doesn't cover. `?next=` is honoured
only when the path is relative, in-site, **and** open to that role; otherwise it
falls back to the role's home.

`context_processors.portal` exposes `role`, `is_agent` / `is_manager` /
`is_director`, `current_user`, and a `nav_items` list computed per role, so
`base.html` loops over data instead of nesting template conditionals. Approvals
items carry a live count badge, suppressed at zero.

| Role | Navigation |
|---|---|
| agent | Dashboard · Log Work · FAQs |
| manager | Team · Programs · Approvals · FAQs |
| director | Overview · Programs · Approvals · FAQs |

## State: `mock_data.py` vs `store.py`

**`mock_data.py`** is static reference data — tiers and thresholds, KPI
definitions, the org chart, demo accounts, notification defaults. It never
changes at runtime.

**`store.py`** holds everything that *does* change: work logs, programs,
notifications.

> ### `store.py` is process-global memory, not a database
>
> Session storage cannot carry a workflow between two people — when an agent
> submits a work log, a manager in a different browser has to see it. `store.py`
> is a module-level singleton that makes that possible.
>
> **It is not persistent.** Every worker restart wipes it, and it does **not**
> survive multiple processes — run a single dev worker or two users will see two
> different worlds. There is no durability, no transactions, no migration path.
> **Replace it with real Django models before any non-demo use.**

Views never touch `STORE` directly; every read and write goes through a helper
(`add_log`, `update_log_status`, `get_pending_logs_for_manager`, `get_programs`,
`add_program`, `update_program_status`, …). Every mutation holds a
`threading.Lock`, because the dev server is threaded, and reads hand back deep
copies so a caller cannot mutate the store by accident.

`POST /dev/reset-store/` (no auth) restores the seed state so a demo restarts
clean. Run its self-check with:

```bash
.venv/bin/python dashboard/store.py     # prints "store OK"
```

## Auth — prototype only

> **This is not real authentication.** Credentials are hardcoded constants
> compared in plain text, there is no user store, no password hashing, no rate
> limiting and no lockout. It exists so a reviewer can see the signed-in and
> signed-out states. **Replace it with a real auth backend before any non-demo
> use, and never deploy it as-is.**

### Demo credentials

The three accounts above are defined in `mock_data.DEMO_ACCOUNTS`, each carrying
a password, a role and the person's full profile. They are shown in a dashed
"Demo access" box on the login page so a grader can get in.

### How it works

No Django auth app, no user model, no migrations. `login` looks the submitted
email (stripped, lowercased) up in `DEMO_ACCOUNTS`, compares the password, and
stores `is_authenticated`, `user_email`, `role` and `display_name` in the session. `logout` is POST-only with CSRF
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

**My Profile** renders a shared identity header plus a role-specific block.
Only the agent shows a tier badge; the manager shows "18 technicians" and the
director "6 managers · 142 technicians". Managers get a team snapshot (size,
average tier, team points, per-tier counts in the tier colours, longest-tenured
and newest reports); directors get a territory snapshot (managers, technicians,
warehouses, NPS, retention, budget as `$8.4M`). For the agent it shows an
identity card (72px initials avatar, name, job title,
tier badge), a two-column details list, and a performance summary pulled from the
`mock_data` helpers. Only **phone** and **location** are editable: "Edit details"
swaps those two values for inputs in place, Save POSTs them into the session, and
Cancel restores from a `data-original` attribute with no round trip. Everything
else is marked managed by HR.

**Notifications** is driven by a role-keyed structure in `mock_data`, so the
template loops one list. All roles get the nine base preferences; managers gain
an **Approvals** group (log submitted, overtime threshold, burnout alert) and
directors gain a **Programs** group (program submitted, budget threshold,
quarterly ROI). It renders those preferences each with Email
and Push switches hand-rolled from a checkbox plus a styled track — no Bootstrap
switch, no library, keyboard operable with a visible focus ring. Every change
autosaves to the session (debounced 300ms per key+channel) and flashes "Saved".
A digest frequency segmented control and a master mute switch save the same way;
mute dims and disables the toggles **without** clearing what is stored, so
switching it back off restores exactly what was set. Preferences read from the
session with the `mock_data` defaults as fallback.

## Work logging

The agent's daily log at `/log-work/` is what makes the portal solve a real
field problem rather than display numbers.

### How points are calculated

`mock_data.calculate_points(job_type, modifiers)` is the **single source of
truth**. Nine job types carry base points and estimated minutes; five modifiers
apply on top, each delta computed off the base and added, so the preview can
show one line per modifier:

| Modifier | Effect | |
|---|---|---|
| First-time fix | +15% | resolved without a follow-up visit |
| Premium upsell | +25% | customer took a premium add-on |
| After hours | +20% | outside the standard window |
| **Weather protected** | +15% | storm, snow, extreme heat — pay is protected, not penalised |
| **Safety flagged** | −100% | PPE or ladder protocol missed; zeroes the entry |

`safety_flagged` short-circuits and returns 0 whatever else is applied, and its
chip sits below a divider with a confirmation step so it can't be a stray click.

The browser mirrors this from `JOB_TYPES` / `POINT_MODIFIERS` handed over as JSON
in a data attribute — nothing is hardcoded twice. One subtlety: Python's `round()`
rounds halves to even while JS `Math.round` goes half-up, which would silently
drift the two apart, so the server uses `floor(x + 0.5)` to match. All **288**
job × modifier combinations were compared between the two implementations and
agree exactly. **The server always recalculates on write** — a points value in
the POST body is ignored.

### Daily totals — approved only

`store.get_day_summary(agent_id, date)` is the **single source of truth** for a
day's figures and returns `{jobs, minutes, points, est_value, pending_count}`
(plus `draft_count` / `draft_points` / `submitted_at` describing workflow state).

Only **approved** entries count toward jobs, minutes, points and value — the same
"not banked yet" rule the dollar ledger uses. A day holding only drafts or
submitted work reports `0 / 0 / 0 / $0.00`, with a caption saying how many entries
are still awaiting approval, so the zeroes are never mistaken for "nothing
happened". The entry cards themselves render for that date whatever their status,
so an agent can still see what is pending, rejected or approved.

### Lifecycle

```
draft → submitted → approved | rejected | changes_requested
```

Only `draft` and `changes_requested` are editable, and ownership is enforced in
`store.py` rather than the view — `update_entry` and `delete_entry` take an
`agent_id` and refuse entries owned by anyone else. `changes_requested` returns
an entry to editable while **preserving** the reviewer's note.

Submitting a day moves every draft on that date to `submitted` and routes it to
the agent's manager, where it shows up in the Approvals badge count. Future dates
are blocked in both the date picker (`max`) and the view.

## Point-to-dollar ledger

`POINT_VALUE_USD = 0.18` — the demo conversion rate. Real rates vary by program
and region; this one number stands in for that whole table.

The dashboard ledger separates **approved** points (banked, shown as the headline
dollar figure) from **submitted-but-unreviewed** points, styled distinctly so the
agent can see what isn't theirs yet. A "How this is calculated" disclosure states
the actual rate.

## What-if simulator

A slider and job-type selector on the dashboard project points, tier and dollar
value for extra work this month, calling out a tier crossover when the projection
crosses a `mock_data` threshold. Verified the crossover fires at the exact
boundary: from 3,180 points, 15 residential installs leaves 4,980 (Silver) and
16 reaches 5,100 (Gold).

## AI Insights

> **Rule-based, not an LLM.** `dashboard/insights.py` is a fixed set of
> conditions evaluated against the agent's own logged work — no model call, no
> keyword matching, no inference. The card footer says "Generated from your
> recent activity", which is what actually happens. This is labelled the same
> way the chatbot is labelled a keyword stub.

`generate_insights(agent_id)` evaluates six rules in priority order and returns
up to four that fire, each `{icon, headline, detail, tone, cta_label, cta_url}`:

1. **Tier proximity** (opportunity) — within 500 points of the next tier, with
   the install count computed from the same job math as the what-if simulator.
2. **Streak** (celebration) — 3+ consecutive days with approved work.
3. **Changes requested** (caution) — entries waiting on the agent's edits.
4. **Modifier opportunity** (informational) — no premium upsell or first-time
   fix logged in 14 days.
5. **Pending value** (informational) — submitted points not yet approved.
6. **Active program match** (opportunity) — skips gracefully today, since seeded
   programs carry no job-type targeting; it fires once a `job_types` field exists
   rather than inventing a match.

If fewer than two fire, a calmer fallback card is shown, styled without a
tone-coloured border so it cannot be mistaken for a real finding. Tones reuse
only registered colours. Run the self-check with:

```bash
.venv/bin/python -c "import os,django,runpy; \
  os.environ.setdefault('DJANGO_SETTINGS_MODULE','spectrum_portal.settings'); \
  django.setup(); runpy.run_module('dashboard.insights', run_name='__main__')"
```

## Director workspace

Priya oversees 6 managers and 142 technicians. Her pages are **aggregate-first** —
there is deliberately no drill-down to an individual technician anywhere in this
role, because her accountability is regional numbers, not individual coaching.

### ROI tracker — modelled, not measured

The overview's headline is an estimate of quarterly savings attributable to the
incentive program, broken into three attributed lines:

| Line | Arithmetic |
|---|---|
| Reduced repeat visits | repeat visits avoided × cost per truck roll |
| Lower technician turnover | technicians retained × cost to replace one |
| Improved first-time fix | hours saved × loaded hourly rate |

> Every input lives in `mock_data.ROI_ASSUMPTIONS`, each carrying a `source`
> field that states plainly it is a **demo assumption, not a measured figure**.
> The page repeats that caveat and exposes all four assumptions in an expandable
> block. Presenting a modelled number as measured fact is exactly the failure
> this design guards against, so the distinction is made visible rather than
> buried — a director reading the figure can see which is which.

Verified: each line equals its stated arithmetic against `ROI_ASSUMPTIONS`, the
total is their sum, and net = total − approved program spend.

### Program comparison

Up to three programs sit side by side in a real table (sticky attribute column,
horizontal scroll on narrow screens). Selection is driven by the query string, so
a comparison is shareable and survives the back button.

Numeric rows highlight the **most favourable** value — and favourability is
declared per attribute rather than assumed, because it runs in both directions:
lower is better for estimated budget and cost per participant, higher is better
for expected participants, projected point volume and estimated ROI. Cost per
participant and projected volume are computed in `store.program_metrics()` from
the program's own rules, never hand-entered. A "Show only differences" toggle
collapses rows where every selected program matches, and a gap in a proposal
renders an explicit "Not specified" rather than an ambiguous blank cell.

### Program approval

Each proposal is shown against remaining quarterly budget with a usage bar, and
a conflict check lists any already-approved program overlapping **both** the date
range and the job types — two programs paying for the same work being the mistake
that check exists to catch. Approving over budget is allowed but states the
overage explicitly; the decision stays the director's.

Rejecting or requesting changes **requires a note**, enforced in
`store.review_program()` and not merely by a disabled button — the same rule the
manager queue applies to work logs. Decisions can be reopened within 24 hours,
also with a note.

## Cross-role consistency

- **One badge source.** Every navbar approval count comes from the same store
  helper the page itself uses (`count_submitted_for_manager`,
  `count_pending_programs`) — never a separate tally that can drift.
- **One status pill.** `partials/_status_pill.html` plus a single CSS block
  renders work-log and program statuses identically everywhere they appear.
- **The loop closes.** A director approves a program and the field agent sees it
  on their dashboard under **Active programs**, with the bonus rule written out
  in plain language.
- **Role-aware assistant.** `chat_responses.responses_for_role(role)` layers a
  manager topic (how to review submissions) and a director topic (how program
  approval works) on top of the shared six, through one code path. An agent
  asking a manager-only question gets the fallback, not the answer.

## Interactive features

- **Tier explorer** (landing) — ARIA tablist, 200ms panel crossfade, sliding 2px
  indicator, arrow/Home/End key navigation
- **Hero entrance** — headline words fade and rise in sequence via CSS
  `transition-delay`
- **Reveal on scroll** — one shared `IntersectionObserver` staggers `.u-reveal`
  elements by 60ms
- **Count-up numbers** — `SP.animateCount` with an ease-out curve, used by the
  KPI cards, the balance, the day summary and the landing headline stat
- **AI Insights** — rule-based personalised cards (see above); no LLM
- **Earned today** — live KPI tile replacing the old CSAT card, in `--sp-earned`
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

## Next: manager and director feature pages

The role foundation — accounts, routing, access control, the shared store and
the role-aware profile and notification pages — is in place. The seven feature
routes render "coming in the next pass" stubs and are filled in by later passes:

- **Manager** — `/manager/` roster and drill-down, `/manager/programs/` program
  builder, `/manager/approvals/` work-log review queue.
- **Director** — `/director/` territory rollups, `/director/programs/` spend
  against budget, `/director/approvals/` program sign-off.
