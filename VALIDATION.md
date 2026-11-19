# SpeakEasy validation report — stateless Vercel build

## Architecture corrections

- Removed server-side SQLAlchemy persistence.
- Removed the SQLite/PostgreSQL database connection module and ORM model module.
- Removed database drivers and `DATABASE_URL` configuration.
- Removed the signed guest cookie and all server-side visitor/session state.
- Removed server-side usage reservation, session history, retry persistence, and cleanup endpoints.
- Removed the Vercel scheduled database-cleanup cron.
- Replaced server-side history and usage tracking with browser IndexedDB in `public/static/js/local-store.js`.
- Kept Python FastAPI for HTML rendering, security headers, scorecard validation, and exact composite-score calculation.
- Kept Firebase AI Logic as the only Firebase integration; App Check is used only to protect AI Logic requests.

## Persistence behavior

Vercel functions do not retain application filesystem writes between invocations. This build does not attempt to write a database or user session files to the Vercel filesystem.

Completed sessions, transcripts, scorecards, retry status, and the daily convenience allowance are stored in the user's browser IndexedDB. Records are removed after 30 days when the local store is accessed, including during application startup. Browser data is not synchronized between devices. Clearing browser site data removes history and resets the local allowance. The daily allowance is therefore a client-side convenience cap, not tamper-proof enforcement.

## Automated checks

- `python -m pytest -q`: **29 passed**.
- `python -m compileall -q main.py app tests`: passed.
- Node syntax check for `app.js`, `firebase-ai.js`, and `local-store.js`: passed.
- `vercel.json` JSON parse: passed.
- FastAPI route smoke tests: `/`, `/health`, CSS and JavaScript static assets returned HTTP 200.
- Removed `/api/sessions` and `/api/usage` endpoints return HTTP 404.
- Structure tests confirm there are no database modules, database drivers, database environment variables, or database files in the project.
- Scorecard validation still enforces exact transcript quotations and recomputes the primary four-metric average in Python.
- Branded 404 and 500 pages remain in place.

## Not verified in this environment

- Live Firebase AI Logic requests and Gemini Nano inference on a configured Chrome device.
- Real microphone and speech recognition end-to-end behavior in a physical browser.
- Full keyboard/screen-reader accessibility audit.
- A live Vercel deployment.

The automated checks do not replace those external acceptance tests.
