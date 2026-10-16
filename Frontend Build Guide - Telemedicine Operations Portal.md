# Frontend Build Guide: Telemedicine Operations Portal

For Antigravity · Replaces the Streamlit dashboard · October 2026

## Start here

Fix the facts first and the design second: the current dashboard shows details that contradict your report, and a panel can spot them in 30 seconds. Section 1 lists every problem found in your six screenshots. Section 2 picks a build track. Sections 3 to 6 define the portal, its design system, its tech stack and the API it needs. Section 7 holds the prompts to paste into Antigravity, in order.

## 1. What the six screenshots show

Rows 1 to 5 hurt credibility, rows 6 to 13 hurt readability, and rows 14 to 16 are missing product.

| # | Where | Problem | Fix |
| --- | --- | --- | --- |
| 1 | Architecture panel and sidebar (images 5, 6) | Says storage is SQLite, auth is Mock Cognito and the model is BiLSTM. Your report and speech say Neon PostgreSQL, JWT with bcrypt and a stacked LSTM. | Decide what is true. Generate every such label from a live /system/info endpoint so the UI can never drift from the backend. |
| 2 | Sidebar team block (image 6) | Tanmay is shown as 24BIT0537; the course sheet says 24BIT0079. | Confirm the roll number and keep team details in one config file. |
| 3 | Decision Reasons vs Total Events (images 1, 3) | The bars add to 500 (380 + 88 + 32) but Total Events is 518. | Every decision must store a reason. Add a database constraint and a test that the totals match. |
| 4 | Events table (image 4) | Five identical WEARABLE rows at 04:01:27 and two identical ECG-101 override rows (210.5 ms, criticality 9.5): leftover test data mixed with live data. | Add a source field (live, simulated, test), a unique key on device and timestamp, and hide test data by default. |
| 5 | Alerts Sent metric (image 1) | Shows 32, the same as Emergency Overrides, so it counts overrides, not delivered messages. | Store every Telegram and email attempt with its status. Show delivered and failed separately. |
| 6 | Latency trend (image 2) | The data sit in two bursts two days apart, so the line is two vertical bars and the time axis is useless. The chart says predicted latency while the table and feed say RTT. | Plot predicted and observed latency as two series on a real, zoomable time axis. |
| 7 | Times (images 4, 6) | Events show 04:54 while the page says refreshed at 12:02, with no timezone anywhere. | Store UTC, display one chosen timezone (default Asia/Kolkata) and label it everywhere. |
| 8 | Section titles and legends (images 1 to 4) | Pale grey-blue text on white is hard to read, especially on a projector. | Meet WCAG AA contrast (4.5 to 1) for all text. |
| 9 | Chart panels | Dark grey chart boxes sit on a white page, so two visual styles collide. | One theme per mode (light and dark). |
| 10 | Colour meaning (images 1 to 3) | CLOUD is blue in the donut and scatter but green in the trend chart. EDGE is red everywhere, which reads as danger even for routine edge routing. | One colour per meaning (palette in section 4). Red only for emergencies. |
| 11 | Metric cards (image 1) | Green up-arrows on 25.9%, 74.1% and Telegram + Gmail imply growth that is not measured. | Show a delta only when comparing with a stated earlier period. |
| 12 | Events table (image 4) | Values such as 237.810000 and 0.700000, a meaningless index column and truncated device names. | Format numbers to one decimal, drop the index, widen columns and add a row drawer. |
| 13 | Live Alert Feed (image 4) | Lists routine \[CLOUD\] decisions as alerts, duplicates the table and shows only ECG-101. Real alerts get lost. | Show only alerts, with severity, delivery status and acknowledge. |
| 14 | Whole page | One long scroll, the Streamlit Deploy menu is visible, simulator buttons sit in the operations sidebar and there is no navigation. | A multi-page portal with role-based navigation. Simulator for admin only. |
| 15 | Scatter chart (image 3) | Criticality is only 0 to 3 or 8 to 10 with nothing in between, the toolbar covers the legend, and the reason bars use a third colour scheme. | State that the stream is simulated, add mid-range patients, move the legend and reuse the palette. |
| 16 | Missing entirely | Sign-in view, device view, alert acknowledgement, audit-chain verification, model information, thresholds, empty and error states, mobile layout. | The pages in section 3. |

## 2. Pick a track

- Track A, quick fix (about one day): keep Streamlit and fix rows 1 to 13. Use it only if your review is within three days.
- Track B, recommended (about four to six working days with an agent): a React portal that reads the FastAPI backend. Keep Streamlit running as a fallback until Track B passes the checklist in section 9.

Track A prompt:

```
PROMPT - TRACK A
Open dashboard/app.py and fix, in order:
1. Replace every hard-coded architecture, storage, auth, model and team label with values read from a new GET /system/info endpoint that reports what the running backend really uses.
2. Make Decision Reasons add up to Total Events, or show an Uncategorised bar.
3. Hide rows whose source is not live by default (add a Show test data toggle).
4. Alerts Sent = delivered Telegram and email attempts; show failures separately.
5. Show one timezone (Asia/Kolkata) in every timestamp, with its label.
6. One colour map for every chart: CLOUD #2563EB, EDGE #0F766E, emergency #DC2626, network veto #B45309.
7. Format floats to one decimal, drop the index column, widen Device.
8. Live Alert Feed shows only alerts.
9. Set toolbarMode = minimal in .streamlit/config.toml and use a light theme with AA contrast.
10. Latency chart: predicted and observed as two series on a real time axis, with labelled 75, 150 and 300 ms bands.
ACCEPTANCE: before and after screenshots; totals match; no test rows visible by default.
```

## 3. The portal to build (Track B)

Name: Telemedicine Operations Portal. Roles: admin, doctor, auditor.

| Page | Who | What it shows | Key interactions |
| --- | --- | --- | --- |
| Sign in | Everyone | Username and password, error and lockout messages. No default credentials on screen. | Sign in, sign out |
| Overview | All roles | KPI row (decisions, EDGE share, CLOUD share, emergency overrides, network vetoes, alerts delivered and failed, average pipeline time, model version), predicted vs observed latency with 75, 150 and 300 ms bands, routing split, decision reasons, latest alerts. | Date range, device filter, source filter, timezone |
| Live Monitor | All roles | Streaming table of decisions. | Pause, filter, row drawer explaining why: inputs, vetoes checked, AHP weights, scores, audit hash |
| Devices | All roles | A card per device type with status, last seen, current risk and a 24 hour sparkline. Detail view with latency and criticality timelines. | Open device, change range |
| Alerts | Doctor and admin act; auditor reads | Severity, delivery status per channel (Telegram, email), acknowledged by. | Acknowledge, filter |
| Decision Lab | All roles | Sliders for criticality, predicted latency and cost. Shows each veto check, normalised values, weights, edge and cloud scores and the final decision. | Drag sliders, replay a stored decision |
| Model and Data | All roles | Version, architecture, training data size, MAE and RMSE against a simple baseline, predicted vs actual chart, risk bands. | Switch dataset split |
| Audit | Auditor and admin | Hash-chained log with a Verify chain button that reports OK or the first broken row. | Verify, export CSV |
| System | Admin and auditor | A live architecture diagram with component health and counts per stage, database engine and region, versions, AWS migration table. | Open component |
| Admin | Admin | Users and roles, thresholds (read-only unless you build audited editing), simulator console with scenarios normal, degradation, cardiac emergency and mixed. | Start, stop, set rate |

Decision Lab is the strongest feature for your review: a panelist can drag a slider and watch the engine decide.

## 4. Design system

Principles:

1. Colour carries one meaning. Red is for emergencies only.
2. Every number, label and status comes from the API. Nothing about the architecture is typed into the UI.
3. Clinical calm: white and grey surfaces with one accent colour.
4. Every state is designed: loading, empty, error, offline and no permission.
5. Projector friendly: 16 px body text, 36 px KPI numbers.

| Meaning | Token | Light | Dark |
| --- | --- | --- | --- |
| Routed to CLOUD | --cloud | #2563EB | #60A5FA |
| Routed to EDGE | --edge | #0F766E | #2DD4BF |
| Emergency override | --emergency | #DC2626 | #F87171 |
| Network veto | --veto | #B45309 | #FBBF24 |
| Healthy or delivered | --ok | #15803D | #4ADE80 |
| Page background | --page | #F1F5F9 | #020617 |
| Card surface | --surface | #FFFFFF | #0F172A |
| Text | --text | #0F172A | #E2E8F0 |
| Muted text | --muted | #475569 | #94A3B8 |

Check every text and background pair with a contrast tool and require WCAG AA. Never rely on colour alone: use marker shapes in charts (circle for CLOUD, square for EDGE, triangle for emergency, diamond for veto).

```css
:root {
  --page:#F1F5F9; --surface:#FFFFFF; --text:#0F172A; --muted:#475569;
  --cloud:#2563EB; --edge:#0F766E; --emergency:#DC2626; --veto:#B45309; --ok:#15803D;
}
.dark {
  --page:#020617; --surface:#0F172A; --text:#E2E8F0; --muted:#94A3B8;
  --cloud:#60A5FA; --edge:#2DD4BF; --emergency:#F87171; --veto:#FBBF24; --ok:#4ADE80;
}
```

Layout: a collapsible left sidebar (240 px), and a top bar with a live status pill (Live, Reconnecting, Offline), timezone selector, theme toggle and user menu. Content width up to 1440 px on a 12-column grid. Breakpoints at 1280, 768 and 390 px.

Format rules:

- Latency: 38.6 ms. Criticality: 9.5 / 10. Percentages: 25.9%. Counts: 1,284.
- Time: 15 Oct 2026, 12:02:46 IST, with the relative time on hover.
- Device names are never truncated. Reason codes are shown as words (Network degradation veto, not network\_degradation\_veto).

Chart rules:

- Real time axis with zoom, and downsampling for long ranges.
- Predicted and observed latency as two series, with the 75, 150 and 300 ms thresholds drawn as labelled bands.
- Legends sit outside the plot and the chart toolbar never overlaps them.
- Every chart has a data-table alternative for screen readers.
- A shares chart is a donut or bar with exact counts, never an up-arrow.

## 5. Tech stack

| Concern | Choice | Why |
| --- | --- | --- |
| Framework | React 18, TypeScript, Vite | Fast, typed, industry standard |
| Styling | Tailwind CSS and shadcn/ui | Consistent components, easy theming |
| Charts | Recharts | Simple, enough for these charts |
| Data | TanStack Query | Caching, retries, loading and error states |
| Routing | React Router | Pages and role guards |
| Live updates | Server-Sent Events with polling fallback | Simpler than WebSockets for one-way data |
| Validation | Zod | Rejects malformed API responses |
| Tests | Vitest, Testing Library, Playwright | Unit and end-to-end coverage |
| Packaging | nginx container in docker compose | One command to run |
| AWS target | S3 and CloudFront with Amazon Cognito | A truthful mapping for the frontend |

Why not Streamlit: no real navigation, role control or live push, and it looks like a prototype. Why not Next.js: no server rendering is needed, and a static build maps directly to S3.

EventSource cannot send an Authorization header, so authenticate the stream with an httpOnly cookie or a short-lived ticket from POST /api/v1/stream/ticket.

```ts
import { useEffect, useState } from 'react';

type LiveState = 'live' | 'reconnecting' | 'offline';

export function useLiveStream<T>(url: string, onEvent: (e: T) => void) {
  const [state, setState] = useState<LiveState>('reconnecting');
  useEffect(() => {
    const es = new EventSource(url, { withCredentials: true });
    es.onopen = () => setState('live');
    es.onmessage = (m) => onEvent(JSON.parse(m.data) as T);
    es.onerror = () =>
      setState(es.readyState === EventSource.CLOSED ? 'offline' : 'reconnecting');
    return () => es.close();
  }, [url]);
  return state;
}
```

## 6. Backend contract the frontend needs

All paths sit under /api/v1. Timestamps are UTC ISO-8601. Errors use one shape: an error object with a code and a message. Existing endpoints must not break; add what is missing.

| Endpoint | Who | Returns |
| --- | --- | --- |
| POST /auth/login | Public | Access token and user (username, role). Refresh token in an httpOnly cookie. |
| POST /auth/refresh, GET /auth/me | Signed in | New access token; current user |
| GET /metrics/summary (from, to, device, source) | All roles | Totals, shares, counts by reason, alerts delivered and failed, average pipeline ms |
| GET /metrics/timeseries (bucket, from, to, device) | All roles | Per bucket: predicted latency, observed latency, counts per decision |
| GET /decisions (cursor, limit, filters) | All roles | A page of decisions and the next cursor |
| GET /decisions/{id} | All roles | The decision, its explanation trace and its audit hash |
| POST /decision/explain | All roles | The same trace for hypothetical inputs; nothing is stored |
| GET /devices, GET /devices/{id} | All roles | Status, last seen, risk, recent series |
| GET /alerts, POST /alerts/{id}/ack | Read: all. Ack: doctor, admin | Alerts with a delivery attempt per channel |
| GET /audit, GET /audit/verify | Auditor, admin | Rows; ok, first broken id, rows checked |
| GET /model/info | All roles | Version, architecture, training data size, metrics against baseline, thresholds |
| GET /system/info | Admin, auditor | Database engine and region, auth type, broker, versions, component health |
| GET /stream, POST /stream/ticket | Signed in | Server-Sent Events: decision and alert |
| POST /sim/scenarios/{name}, DELETE /sim | Admin | Start or stop the simulator |

The explanation trace, shown here for a routine patient on a failing network:

```json
{
  "inputs": {"criticality": 1.2, "predictedLatencyMs": 320.0, "costIndex": 0.4},
  "vetoes": [
    {"name": "emergency_override", "threshold": 9.0, "value": 1.2, "fired": false},
    {"name": "network_veto", "threshold": 300.0, "value": 320.0, "fired": true}
  ],
  "ahp": null,
  "decision": "EDGE",
  "reason": "network_degradation_veto"
}
```

When no veto fires, the ahp field holds the weights (0.6396, 0.2583, 0.1021), the normalised criteria and the edge and cloud scores.

## 7. Prompts for Antigravity

Paste the master rules at the start of every session, then one phase prompt at a time. Commit after each phase.

```
MASTER RULES - FRONTEND
1. Every number, label and status in the UI comes from an API response. No hard-coded architecture, storage, auth, model or team text except in one config file.
2. Never display credentials, tokens or personal data (no passwords, chat IDs or email addresses).
3. Hiding things by role is only convenience. The backend enforces access.
4. Use design tokens only. No raw hex colours in components. One colour per meaning.
5. Design every state: loading, empty, error, offline, no permission.
6. Do not change backend decisions. Any backend change needs a test proving old results are identical.
7. A phase is done only when type-check, lint, unit tests and end-to-end tests pass and you have pasted the output.
```

### Phase F0: API audit and data truth (about 0.5 day)

```
PROMPT - F0
Read the whole repository.
1. List every existing HTTP endpoint (method, auth, request, response) in docs/API_AUDIT.md.
2. Compare it with the contract in section 6 of the guide and list the gaps.
3. Find which database the running backend really uses, which auth it uses and which model class is deployed. Make GET /api/v1/system/info report exactly that. Tell me where the existing report or dashboard text disagrees.
4. Add a source column (live, simulated, test) to decisions and a unique key on device and timestamp. Write a cleanup script that marks existing test and duplicate rows as test.
5. Make every decision store a non-null reason.
6. Log every Telegram and email attempt in an alert_deliveries table with status.
7. Add the missing endpoints under /api/v1 without breaking existing ones, with tests.
8. Refactor the decision engine to return an explanation trace with identical decisions. Add a regression test over 1,000 random inputs comparing old and new results.
ACCEPTANCE: pytest passes, API_AUDIT.md shows no gaps, and the /system/info output is pasted.
```

### Phase F1: scaffold, design system and sign-in (about 1 day)

```
PROMPT - F1
Create frontend/ with Vite, React, TypeScript, Tailwind and shadcn/ui. Implement the design tokens from section 4 with light and dark themes. Build the app shell: sidebar, top bar with live status pill, timezone and theme controls, user menu. Add a router with role guards, a typed API client with Zod validation, and token handling (access token in memory, refresh through an httpOnly cookie). Build the sign-in page with loading, error and lockout states. Add a dev-only /dev/components page showing the KPI card, badges, table, chart card, and empty and error states.
ACCEPTANCE: sign-in works against the real API for each role, unauthorised routes show a permission screen, lint and type-check are clean.
```

### Phase F2: Overview and Live Monitor (about 1 to 1.5 days)

```
PROMPT - F2
Build Overview and Live Monitor as described in section 3, following the format and chart rules in section 4. Overview: KPI row, predicted vs observed latency chart with labelled 75, 150 and 300 ms bands and veto markers, routing donut, decision reasons bar (sum must equal total), latest alerts strip, and filters for range, device and source (default live). Live Monitor: a virtualized table fed by Server-Sent Events with pause and resume, filters, and a row drawer showing the explanation trace, inputs, scores and audit hash.
ACCEPTANCE: with the simulator running, new rows appear within 2 seconds without reload; Overview counts equal the API counts; a Playwright test covers both pages.
```

### Phase F3: Devices, Alerts and Decision Lab (about 1 day)

```
PROMPT - F3
Build Devices (grid and detail), Alerts (list, acknowledge, delivery status per channel) and Decision Lab (sliders, step-by-step trace, replay a stored decision). Decision Lab calls POST /decision/explain and shows every veto check and the AHP maths; its result must equal what the engine stored for the same inputs.
ACCEPTANCE: acknowledging an alert as doctor works; as auditor the button is hidden and the API rejects it (test both); Decision Lab output matches 20 sampled stored decisions.
```

### Phase F4: Model, Audit, System and Admin (about 1 day)

```
PROMPT - F4
Build Model and Data (version, architecture, training data size, MAE and RMSE against baseline, predicted vs actual chart), Audit (table, Verify chain button, CSV export), System (live architecture diagram from /system/info with component health and counts, AWS migration table) and Admin (users and roles, thresholds read-only, simulator console with scenarios normal, degradation, cardiac emergency and mixed, plus start, stop and rate).
ACCEPTANCE: System page values equal the backend config; Verify chain returns OK on clean data and flags a deliberately altered copy in a test database; each simulator scenario visibly changes the charts.
```

### Phase F5: polish, accessibility, tests and Docker (about 1 day)

```
PROMPT - F5
Make the layout responsive at 1440, 1024 and 390 px. Add keyboard navigation, focus rings, ARIA labels and data-table alternatives for charts, reduced-motion support, an error boundary and skeleton loaders. No console errors. Add Vitest unit tests and Playwright end-to-end tests for the three roles. Reach a Lighthouse accessibility score of at least 90. Add an nginx Dockerfile, a frontend service in docker-compose.yml and a Content-Security-Policy.
ACCEPTANCE: docker compose up serves the portal; all test output is pasted.
```

### Phase F6: demo pack (about 0.5 day)

```
PROMPT - F6
Create docs/DEMO.md with the exact click path, scenario order and expected numbers. Save light-mode screenshots of every page at 1440 px in docs/screens/. Add one command that resets the database to a clean seeded demo state.
ACCEPTANCE: following DEMO.md on a clean machine produces the screens described.
```

## 8. Demo-day flow

1. Sign in as doctor and open Overview on the clean demo data.
2. Start the normal-day scenario: most decisions go to CLOUD.
3. Start the degradation scenario: latency rises, veto markers appear and the EDGE share climbs.
4. Start the cardiac emergency scenario: an alert appears, the phone buzzes, then acknowledge it on the Alerts page.
5. Open Decision Lab: drag criticality above 9 to show the override, then set latency to 320 ms to show the network veto.
6. Open Audit and click Verify chain. Then Model and Data for accuracy against the baseline, and System for the real stack and the AWS mapping.

## 9. Acceptance checklist

- [ ] No text in the UI contradicts the report, the speech or the backend config.
- [ ] Decision reasons add up to total decisions; test and duplicate rows are hidden by default.
- [ ] Alerts delivered and failed come from stored delivery attempts.
- [ ] One timezone, labelled, in every timestamp.
- [ ] One colour per meaning in every chart, with marker shapes as well.
- [ ] Text contrast meets WCAG AA; Lighthouse accessibility is at least 90.
- [ ] All three roles tested end to end; role restrictions enforced by the API.
- [ ] docker compose up runs the whole stack and the portal.
- [ ] DEMO.md followed once on a clean machine, start to finish.
