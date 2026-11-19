# SpeakEasy

SpeakEasy is a 

## Architecture

```text
speakeasy/
├── main.py                    # FastAPI entry point and HTTP routes
├── requirements.txt           # Python dependencies only
├── vercel.json                # Vercel deployment and daily cleanup schedule
├── .env.example
├── app/
│   ├── config.py              # Environment configuration
│   ├── database.py            # SQLite locally / PostgreSQL on Vercel
│   ├── models.py              # SQLAlchemy persistence models
│   ├── schemas.py             # API request validation
│   ├── scoring.py             # Filler counts and score validation
│   └── security.py            # Signed anonymous browser identity
├── templates/
│   ├── index.html             # Server-rendered user interface
│   ├── 404.html               # Branded not-found page
│   └── 500.html               # Branded server-error page
├── public/
│   └── static/                # Static files served by Vercel CDN
│       ├── css/styles.css     # Vanilla CSS
│       └── js/
│           ├── app.js         # Browser interactions and local speech capture
│           └── firebase-ai.js # Firebase AI Logic browser integration
└── tests/                     # Python API, scoring and architecture tests
```

### Responsibilities

- **Python / FastAPI:** routes, business rules, daily session limits, session persistence, score validation, history and retention.
- **HTML / CSS:** the user interface, served by FastAPI.
- **Plain JavaScript:** native browser interaction, microphone permission, waveform, on-device speech recognition, filler telemetry and the Firebase AI Logic client SDK.
- **Firebase AI Logic:** Gemini Nano prompt generation and Gemini cloud-preferred coaching. The Firebase web SDK is loaded directly from Google's CDN; there is no JavaScript build step.
- **App Check:** the required abuse-protection mechanism for Firebase AI Logic requests. It is initialized only to protect AI Logic. No other Firebase products are integrated.
- **Database:** SQLite for local development. Use persistent PostgreSQL for Vercel deployments. This is application storage, not a Firebase product.

Firebase AI Logic's hybrid web SDK is JavaScript-only. The project therefore keeps the browser integration in `public/static/js/firebase-ai.js`; it does not make the application a JavaScript or TypeScript app. That file imports only Firebase app initialization, Firebase AI Logic, and App Check protection. No Firebase Authentication, Firestore, Storage, Realtime Database, Firebase Admin SDK, or second Gemini SDK is used.

## HTTP error pages

- Unknown browser routes render a branded `templates/404.html` page and return HTTP 404.
- Unexpected browser-side server failures render `templates/500.html` and return HTTP 500.
- API errors remain JSON responses with their original HTTP status codes; internal exception details are logged server-side and are never exposed to the browser.

## Features

### Structured Practice

- Interview, Presentation and Everyday Speaking goals.
- Optional job-description context for interview question generation.
- Fourteen generated questions; the first three unlock immediately.
- Sixty-second speaking sessions.
- One free retry per drill.

### Hot Take Arena

- UX & Product Design, Tech & AI, Workplace Culture and Custom Topic.
- Mild, Spicy and Extra Hot difficulty.
- Extra Hot prompts include a mandatory forbidden word or phrase.
- Five-second preparation countdown and ninety-second response.
- Stance clarity and punchier hook coaching.

### Speech and privacy

- The browser requests on-device speech recognition using `processLocally = true`.
- If on-device speech recognition is unsupported or its language pack is unavailable, the user can type the transcript. The app does not switch to a remote speech-recognition service.
- A Web Audio analyser produces a live waveform. The app does not create an audio Blob or send microphone audio to the server.
- The transcript is sent to Firebase AI Logic for coaching and to the Python API for history. Raw audio is never uploaded or persisted.
- History is stored for 30 days.

### Coaching and scoring

- Six metrics: Content, Structure, Delivery & Pacing, Confidence, Hook and Filler Control.
- Overall score is recalculated by Python as the exact arithmetic mean of Content, Structure, Delivery & Pacing and Confidence.
- Line to Fix must be an exact transcript quote; non-matching model annotations are rejected or ignored.
- Hot Take results include Stance Clarity, a stance verdict and a punchier hook.

**Scoring limitation:** the app does not upload audio for voice analysis. Delivery & Pacing is therefore an estimate based on transcript length and elapsed time. It does not measure actual pitch, volume, pauses, vocal tone or prosody.

**Speech fallback:** if the browser cannot provide local speech recognition, the user types or pastes a transcript. No audio-buffer upload is used, preserving the no-audio-upload privacy requirement.

## 1. Requirements

- Python 3.12 or newer.
- Chrome Desktop 139 or newer for Firebase AI Logic hybrid inference and Gemini Nano.
- A Firebase project with Firebase AI Logic enabled.
- A reCAPTCHA Enterprise site key registered for Firebase App Check.
- For Vercel deployment, a persistent PostgreSQL database and a Vercel account.

No Node.js, npm, TypeScript compiler or frontend bundler is required.

## 2. Local setup

From the project directory:

```bash
python -m venv .venv
```

Activate the environment:

```bash
# macOS / Linux
source .venv/bin/activate

# Windows PowerShell
.venv\Scripts\Activate.ps1
```

Install Python requirements:

```bash
pip install -r requirements.txt
```

Create the environment file:

```bash
cp .env.example .env
```

Fill in the Firebase values described below. For local development, leave `DATABASE_URL` empty; the application creates `data/speakeasy.sqlite3` automatically.

Start the application:

```bash
uvicorn main:app --reload
```

Open `http://127.0.0.1:8000`.

## 3. Firebase AI Logic setup

### Create and enable the project

1. Open the [Firebase Console](https://console.firebase.google.com/).
2. Create a Firebase project (Google Analytics is not required for this app).
3. Open **AI Services → AI Logic**.
4. Select **Get started**.
5. Select the **Agent Platform Gemini API** provider. The code uses `AgentPlatformBackend` and the `global` location.
6. Complete the guided setup and enable the required APIs.

The browser code currently uses `gemini-3.5-flash-lite`. The model can be changed with `FIREBASE_AI_MODEL` without changing Python code.

### Register the web app

1. In Firebase Project Overview, add a Web app.
2. Copy the web configuration values.
3. Set these values in `.env`:

```dotenv
FIREBASE_API_KEY=your-web-api-key
FIREBASE_PROJECT_ID=your-project-id
FIREBASE_APP_ID=your-web-app-id
FIREBASE_AI_LOCATION=global
FIREBASE_AI_MODEL=gemini-3.5-flash-lite
```

The Firebase web configuration is public client configuration, not a service-account credential. Do not put private keys or service-account JSON in the browser.

### Configure App Check for AI Logic

1. In Google Cloud Console, create a reCAPTCHA Enterprise **website score-based** key for your deployed domain.
2. In Firebase Console, open **Security → App Check**.
3. Register the web app with the reCAPTCHA Enterprise provider and enter the site key.
4. Open **Security → App Check → APIs** and confirm that **Firebase AI Logic** is enforced.
5. Add the site key to `.env`:

```dotenv
RECAPTCHA_ENTERPRISE_SITE_KEY=your-recaptcha-enterprise-site-key
```

For local development, leave `APP_CHECK_DEBUG=true`. The code sets `self.FIREBASE_APPCHECK_DEBUG_TOKEN = true` before App Check initializes. Run the app, open the browser console, copy the debug token Firebase prints, and register it under the app's **Manage debug tokens** page in Firebase Console. The provider still needs a reCAPTCHA Enterprise site-key value in the app configuration, but the debug token is used for local attestation. Do not add `localhost` to the production key's allowed domains, do not commit a debug token, and do not use debug mode in production.

For production set:

```dotenv
APP_CHECK_DEBUG=false
```

The app initializes App Check only to protect Firebase AI Logic. It does not use Firebase Authentication, Firestore, Storage or Firebase Admin.

## 4. Configure Gemini Nano in Chrome

1. Use Chrome Desktop 139 or newer.
2. Open `chrome://flags/#prompt-api-for-gemini-nano-multimodal-input`.
3. Enable the flag if it is available, then restart Chrome.
4. Open the app and use **Generate 14 questions** or **Generate Hot Take**. Those user actions start the model preparation step.
5. Keep the browser open while Chrome downloads the on-device model. The first download can take several minutes.

When Nano is already available, prompt generation can run on-device. While Nano is downloading or unavailable, `PREFER_ON_DEVICE` uses the Firebase AI Logic cloud fallback. The app reads `response.inferenceSource` and displays the actual route used.

Coaching uses `PREFER_IN_CLOUD`. It prefers cloud Gemini and uses the hybrid fallback behaviour configured by Firebase AI Logic.

## 5. Data and history

The app does not use Firebase data products.

- Local development: SQLite at `data/speakeasy.sqlite3`.
- Vercel: PostgreSQL through `DATABASE_URL` is required because Vercel function filesystems are ephemeral.
- A signed, HttpOnly guest cookie scopes records to the same browser. There is no sign-in or cross-device account sync in this version.
- The free daily allowance is scoped to this guest cookie. Clearing cookies or using another browser creates a new guest identity and can reset that allowance. This anonymous model is suitable for a no-account prototype, not strong per-person fraud prevention.
- Clearing the browser cookie removes the link to that guest's history. This is disclosed in the Privacy dialog.
- Session data is hidden after 30 days and expired records are deleted during API activity. `vercel.json` also schedules daily cleanup at 04:00 UTC; configure `CRON_SECRET` in Vercel so the scheduled request is authorized.

Example PostgreSQL variable:

```dotenv
DATABASE_URL=postgresql+psycopg://USER:PASSWORD@HOST:5432/DATABASE?sslmode=require
```

Use the connection string from your chosen managed PostgreSQL provider. The database is separate from Firebase AI Logic.

## 6. Deploy to Vercel

1. Push this project to a Git repository.
2. Import the repository into [Vercel](https://vercel.com/).
3. Vercel detects `main.py` as the FastAPI application. `vercel.json` sets the Python function runtime limits, security headers and daily cleanup schedule.
4. Add the following environment variables in Vercel Project Settings:

```dotenv
APP_SECRET=long-random-secret-value
APP_ENV=production
DATABASE_URL=postgresql+psycopg://USER:PASSWORD@HOST:5432/DATABASE?sslmode=require
FIREBASE_API_KEY=your-web-api-key
FIREBASE_PROJECT_ID=your-project-id
FIREBASE_APP_ID=your-web-app-id
RECAPTCHA_ENTERPRISE_SITE_KEY=your-production-site-key
FIREBASE_AI_LOCATION=global
FIREBASE_AI_MODEL=gemini-3.5-flash-lite
APP_CHECK_DEBUG=false
FREE_DAILY_SESSIONS=5
SESSION_RETENTION_DAYS=30
CRON_SECRET=another-long-random-secret
```

5. Add the deployed Vercel domain to the reCAPTCHA Enterprise key's allowed domains.
6. Deploy. No npm build command is required.
7. Test `/health`, generate questions, generate a Hot Take, complete a session, check History, and test a single free retry.

Vercel's scheduled cleanup requires Cron Jobs to be enabled for the selected Vercel plan. Even without the scheduled run, expired sessions are filtered from history and removed on subsequent API requests.

## 7. Test

Install requirements, then run:

```bash
python -m pytest -q
```

Check Python syntax:

```bash
python -m compileall -q main.py app tests
```

The running application does not require Node.js. If Node.js is available on a developer workstation, the two browser modules can optionally be syntax-checked with `node --input-type=module --check < public/static/js/app.js` and the same command for `firebase-ai.js`. This is an optional check only; it is not part of the runtime or deployment build.

Firebase AI Logic model calls and Gemini Nano require a configured Firebase project and a supported Chrome desktop browser; automated unit tests do not replace those live integration tests.
