# SpeakEasy

SpeakEasy is a Python-first speaking practice application. FastAPI serves the application and owns its server-side validation. The browser uses a small amount of plain JavaScript for microphone access, local speech recognition, timers, IndexedDB history, and the Firebase AI Logic web SDK.

## Architecture

- **Python / FastAPI:** page rendering, API routing, scorecard validation, score calculation, security headers, and error handling.
- **HTML / Jinja2:** server-rendered application pages.
- **Vanilla CSS:** all application styling.
- **Plain JavaScript:** browser-only interactions, microphone and speech recognition, and Firebase AI Logic calls.
- **Firebase AI Logic:** the only Firebase integration. It provides Gemini Nano on-device inference and cloud Gemini through the managed AI Logic proxy. App Check protects AI Logic requests.
- **Browser IndexedDB:** completed session history, retry state, and the local daily allowance. Records expire after 30 days.
- **Vercel:** serves the Python application and static assets. The server is stateless and writes no files.

There is deliberately **no server-side database**. The project has no SQLite, PostgreSQL, SQLAlchemy, database connection layer, `DATABASE_URL`, Firebase Firestore, Firebase Authentication, Firebase Storage, Firebase Admin SDK, or server-side session persistence. Do not add a database to Vercel for this version.

### Important persistence limitation

History and the daily practice allowance belong to the user's current browser profile on the current device. They are not synchronized to other devices, and clearing browser site data removes them. Because there is no persistent server-side store or account system, the daily allowance is a convenience limit, not tamper-proof enforcement: a user can reset it by clearing local site data or using another browser/device.

## Interface design

The root route (`/`) is a conversion-focused product landing page: it explains the speaking-practice outcome, demonstrates the product in one interactive preview, explains the practice loop, describes the main capabilities, and repeats one primary call to action. It does not use fabricated testimonials or a separate product identity for either practice format.

The application is served at `/app`. It is one product with one Practice workspace and two selectable practice formats. A single accessible selector switches between Structured practice (interviews, presentations and everyday speaking) and Hot Take (spontaneous thinking and defending a position). Only the selected format is displayed; neither format has a separate product card, separate navigation destination, or separate visual identity. The interface uses one consistent visual system, no eyebrow labels, no footer, no standalone S brand tile, and a prominent Settings button. Settings provide working Light/Dark and Small/Medium/Large text-size controls; preferences apply to both the landing page and application and are retained in local browser storage.

## Features

### Structured practice

- Interview, Presentation, and Everyday Speaking goals.
- Optional job description context for interview question generation.
- Fourteen generated questions, with the first three unlocked immediately.
- Sixty-second speaking drills.

### Hot Take format

- UX & Product Design, Tech & AI, Workplace Culture, and Custom Topic categories.
- Mild, Spicy, and Extra Hot levels.
- Extra Hot includes a forbidden word or phrase.
- Five-second preparation and ninety-second response.
- Stance clarity and punchier-hook coaching.

### Speech and privacy

- The browser requests on-device speech recognition using `processLocally = true`.
- If local recognition is unavailable, the user can type the transcript. The app does not switch to a remote speech recognition service.
- A Web Audio analyser renders a live waveform. The app does not create audio blobs or send microphone audio to the server.
- Transcripts are sent to Firebase AI Logic for coaching. Completed transcripts and scorecards remain in the browser's IndexedDB history for up to 30 days.
- No server-side session or transcript persistence exists.

### Coaching and scoring

- Content, Structure, Delivery & Pacing, Confidence, Hook, and Filler Control metrics.
- Overall score is recalculated by Python as the exact arithmetic mean of Content, Structure, Delivery & Pacing, and Confidence.
- The Line to Fix must be an exact transcript quote.
- Hot Take results include Stance Clarity, a stance verdict, and a punchier hook.
- Delivery & Pacing is estimated from transcript length and elapsed time. It does not measure vocal tone, volume, pauses, pitch, or prosody because audio is not uploaded.

## Requirements

- Python 3.12 or newer.
- A modern browser. Chrome Desktop 139+ is required for the documented Gemini Nano and local speech recognition path.
- A Firebase project with Firebase AI Logic enabled.
- A reCAPTCHA Enterprise site key registered with Firebase App Check for AI Logic.
- A Vercel account for deployment.

No Node.js, npm, TypeScript, frontend bundler, database, or external storage service is required.

## Routes

- `/` — product landing page with one interactive product demonstration.
- `/app` — speaking practice application with one workspace and two selectable practice formats.
- `/health` — deployment health check.

## Local setup

Create and activate a virtual environment:

```bash
python -m venv .venv

# macOS / Linux
source .venv/bin/activate

# Windows PowerShell
.venv\\Scripts\\Activate.ps1
```

Install Python dependencies:

```bash
pip install -r requirements.txt
```

Create your local environment file:

```bash
cp .env.example .env
```

Fill in the Firebase AI Logic values described below, then start FastAPI:

```bash
uvicorn main:app --reload
```

Open `http://127.0.0.1:8000`.

## Firebase AI Logic setup

1. Open the [Firebase Console](https://console.firebase.google.com/) and create or select the client's project.
2. Open **AI Services → AI Logic → Get started**.
3. Select the **Agent Platform Gemini API** provider. The browser integration uses `AgentPlatformBackend` with the `global` location.
4. Complete Firebase's guided setup and enable the APIs it requests.
5. Register a Web app in Firebase Project Overview and copy its public web configuration values.
6. In Google Cloud Console, create a reCAPTCHA Enterprise website score-based key for the deployed domain.
7. In Firebase Console, open **Security → App Check**, register the web app with reCAPTCHA Enterprise, and enforce App Check for Firebase AI Logic.
8. Add the values to `.env`:

```dotenv
FIREBASE_API_KEY=your-web-api-key
FIREBASE_PROJECT_ID=your-project-id
FIREBASE_APP_ID=your-web-app-id
RECAPTCHA_ENTERPRISE_SITE_KEY=your-recaptcha-enterprise-site-key
FIREBASE_AI_LOCATION=global
FIREBASE_AI_MODEL=gemini-3.5-flash-lite
APP_CHECK_DEBUG=true
```

The web configuration values are public client configuration, not service-account credentials. Never add a private key or service-account JSON to the browser.

For local development, the app sets the Firebase App Check debug-token flag before App Check initialization. Run SpeakEasy, open the browser console, copy the debug token Firebase prints, and register it under the web app's **Manage debug tokens** in Firebase Console. Do not commit debug tokens. Set `APP_CHECK_DEBUG=false` in production.

## Gemini Nano setup

1. Use Chrome Desktop 139 or newer.
2. Open `chrome://flags/#prompt-api-for-gemini-nano-multimodal-input` and enable the flag if it is available.
3. Restart Chrome.
4. Generate questions or a Hot Take. The user action starts device-model preparation.
5. Keep Chrome open while it downloads the model. Initial setup may take several minutes.

When Gemini Nano is ready, generation prefers on-device inference. If it is unavailable, Firebase AI Logic can fall back to cloud inference. SpeakEasy reports the actual `response.inferenceSource` value.

## Browser-local history and usage

No server database is configured or needed.

- Completed sessions, transcripts, scorecards, retry state, and daily usage are stored in browser IndexedDB.
- The browser prunes session history after 30 days.
- The daily practice allowance is counted per browser profile and UTC date.
- Clearing browser site data removes history and resets the local allowance.
- History does not sync across devices or browsers.
- The Python API validates coaching output and recomputes the overall score but does not save the transcript or session.

This no-account, browser-local approach is intentional for this Vercel deployment. Do not add SQLite, PostgreSQL, a server-side database, or database environment variables unless the product requirements change to include cross-device accounts or centrally enforced usage limits.

## Deploy to Vercel

1. Push the project to a Git repository.
2. Import the repository into [Vercel](https://vercel.com/).
3. Set the Vercel Root Directory to the folder containing `main.py`, `requirements.txt`, and `vercel.json`.
4. Add these environment variables in Vercel Project Settings:

```dotenv
APP_ENV=production
FIREBASE_API_KEY=your-web-api-key
FIREBASE_PROJECT_ID=your-project-id
FIREBASE_APP_ID=your-web-app-id
RECAPTCHA_ENTERPRISE_SITE_KEY=your-production-site-key
FIREBASE_AI_LOCATION=global
FIREBASE_AI_MODEL=gemini-3.5-flash-lite
APP_CHECK_DEBUG=false
FREE_DAILY_SESSIONS=5
SESSION_RETENTION_DAYS=30
```

5. Add the deployed Vercel domain to the reCAPTCHA Enterprise key's allowed domains.
6. Deploy. Vercel detects `main.py` as the FastAPI entry point and serves static files from `public/`.
7. Verify `/health`, generate a question set, generate a Hot Take, complete a drill, open History, and use the one free retry.

There is no `DATABASE_URL`, external database setup, Vercel Cron job, Node build, or storage service configuration.

## Tests

Install development dependencies and run:

```bash
pip install -r requirements-dev.txt
python -m pytest -q
python -m compileall -q main.py app tests
```

The app does not need Node.js to run. If Node is available, the browser modules can optionally be syntax-checked:

```bash
node --check --input-type=module < public/static/js/app.js
node --check --input-type=module < public/static/js/firebase-ai.js
node --check --input-type=module < public/static/js/local-store.js
```

Automated tests do not replace live Firebase AI Logic, Gemini Nano, microphone, accessibility, or Vercel deployment verification.

## Error pages

- Unknown browser pages return the branded `templates/404.html` with HTTP 404.
- Unexpected browser errors return `templates/500.html` with HTTP 500.
- API errors remain JSON responses with their proper HTTP status.

## Practice experience

SpeakEasy is a single speaking-practice product. Its Practice page contains one shared workspace with two selectable formats: Structured practice and Hot Take. Selecting a format changes the activity shown inside the same workspace. The formats do not have separate landing pages, navigation destinations, product cards, or visual identities. The top navigation is limited to Practice and History.
