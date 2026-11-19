# SpeakEasy build validation

## Implemented architecture

- Python 3.12+ and FastAPI are the application and backend.
- Jinja2 serves the HTML interface, including branded 404 and 500 error pages.
- Vanilla CSS styles the application and error pages.
- Two plain JavaScript modules handle browser-only functions and the Firebase AI Logic web SDK.
- Firebase integration is limited to Firebase AI Logic and App Check protection required for it.
- There is no React, TypeScript, Tailwind, Vite, Node runtime, npm build, Firebase Authentication, Firestore, Cloud Storage, Firebase Admin SDK, or separate Gemini SDK.
- Application records are held in SQLite locally or PostgreSQL when deployed to Vercel.

## Checks run in this environment

- `python -m pytest -q`: **29 tests passed**.
- `python -m compileall -q main.py app tests`: passed.
- Plain JavaScript module syntax checks using Node: passed. Node is used only as an optional development syntax checker, not as an application dependency or runtime.
- CSS parsed with `tinycss2`: no syntax errors.
- HTML templates parsed; template IDs and browser selectors checked for consistency.
- FastAPI route smoke tests: passed.
- Locally served CSS and JavaScript asset requests: passed.
- Unknown browser routes return branded HTML with HTTP 404.
- Unhandled browser errors return branded HTML with HTTP 500 and do not expose exception details.
- Unknown API routes continue to return JSON with HTTP 404.

## Not verified here

- Live Firebase AI Logic requests: require the customer's Firebase project values and an enabled AI Logic provider.
- App Check / reCAPTCHA verification against the customer's project: requires the registered production site key and debug-token setup.
- Live Gemini Nano inference: requires a supported Chrome desktop installation, a downloaded model, and a real browser.
- Browser microphone / speech recognition and visual accessibility: no Chromium browser executable was available in this environment.
- Vercel deployment and PostgreSQL connectivity: require the customer's Vercel project and managed PostgreSQL connection string.
- Loading the Firebase SDK from Google's CDN could not be tested live because outbound DNS/network access was unavailable.

The checks above verify source structure and local Python routes, not production deployment or live AI behavior.
