# SpeakEasy — current design and regression validation

## What changed in this revision

- Replaced the previous marketing-style landing page with a concise page using only the product information in the PRD: 60-second structured practice, 90-second spontaneous takes, specific feedback, and the three-step practice loop.
- Removed the extra feature rows, repeated calls to action, social-proof/pricing-style sections, and footer. The page now has one headline, one concise explanation, one product demonstration, one primary CTA, and one three-step loop.
- Rebuilt the application screen as a speaking-practice tool rather than a generic AI/chat interface.
- Structured practice and Hot Take now use an open two-column working layout: setup on the left, generated questions or prompt on the right.
- Replaced purple accents, gradients, rounded panel cards, and stacked card treatments with a restrained rust accent, typography, working space, and dividers.
- Preserved the same product identity, practice/history navigation, settings, history, timed recording, scorecard, and both practice formats.
- Updated the 404 and 500 pages to use the same Inter wordmark and plain language as the application.

## Design and interaction checks

- The landing page contains exactly two content sections: the hero/product preview and the three-step practice loop.
- The landing page has one primary CTA and does not introduce content beyond the PRD.
- The product preview switches between structured and spontaneous practice prompts and updates the displayed duration.
- The application uses one Practice destination with one accessible tablist for the two formats.
- Structured and Hot Take panels keep their existing IDs and API wiring; the mode selector updates `aria-selected`, keyboard tab stop, and panel visibility.
- Generated Hot Take prompts replace the empty prompt state instead of appearing alongside it.
- Practice setup and prompt/question output use an open, line-based layout rather than generic AI cards or chat bubbles.
- The primary accent is rust rather than purple; no CSS gradients or pill-shaped practice panels are used.
- Existing theme and font-size settings are preserved. Settings text does not expose Firebase, IndexedDB, Gemini, or Gemini Nano implementation details.
- Focus outlines remain on interactive controls, not on content sections or tab panels.

## Automated checks

- `python -m pytest -q`: **41 passed**.
- Python compilation: passed.
- JavaScript ES-module syntax checks: passed for `app.js`, `firebase-ai.js`, `local-store.js`, `preferences.js`, and `landing.js`.
- CSS parser validation: passed with zero syntax errors.
- HTML/template tests: route render, static asset paths, required element IDs, and error page templates passed.
- Existing scoring, usage, local history, IndexedDB recovery, privacy, and AI integration contract tests remain in the suite.

## Browser verification limitation

A live browser screenshot run was attempted, but Chromium navigation to the local application and local HTML files was blocked by the execution environment (`ERR_BLOCKED_BY_ADMINISTRATOR`). The WeasyPrint print rendering is not a substitute for browser layout testing, so no claim is made that real-browser visual or responsive interaction checks passed in this revision.

Before production release, run the landing page and application in Chrome at desktop, tablet, and mobile widths; test both practice tabs; verify Light/Dark and all font-size choices; and test keyboard/screen-reader navigation, microphone capture, Firebase AI Logic, Gemini Nano, and cloud fallback on a supported device.
