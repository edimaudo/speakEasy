# SpeakEasy — validation report

## Reference-led product and landing-page redesign

- Rebuilt the root route as a focused product landing page with a specific speaking-practice promise, one primary call to action, one interactive product preview, a three-step usage explanation, capability details, and a repeated call to action.
- Used the landing-page guidance as a structure reference and the speech-practice app as a product-demonstration reference; no third-party branding or fabricated testimonials are used.
- The root page introduces one product. It does not position Structured practice and spontaneous practice as separate products.
- Kept the product wordmark as text without a standalone initial/brand tile.
- Removed eyebrow/kicker labels and footer elements.

## Unified application experience

- The application is served at `/app`; the root `/` is the marketing landing page.
- The application has one Practice workspace with a single accessible selector for Structured practice and Hot Take.
- Only the selected practice panel is visible. The selected tab, `aria-selected`, keyboard tab stop, and visible panel are synchronized.
- The two formats share typography, colour tokens, controls, action styling, and workspace layout.
- Navigation contains Practice and History; spontaneous practice is not a separate navigation destination.

## Settings and focus behavior

- Settings provide working Light and Dark appearance controls.
- Settings provide Small, Medium, and Large text-size controls.
- Preferences are saved in local browser storage and applied on both the landing page and application before first paint.
- User-facing Settings copy does not mention implementation products or storage technologies.
- Content sections and tab panels do not receive an outline or highlight when focused. Interactive controls retain visible `:focus-visible` indicators for keyboard accessibility.

## IndexedDB error correction

- Database connections are invalidated on `close` and `versionchange` events.
- A transaction creation attempt detects a stale/closing connection and reopens IndexedDB once.
- Transaction-to-connection tracking ensures an aborted old transaction cannot close a newer connection.
- Browser storage failures are translated into user-facing messages; raw IndexedDB “database connection is closing” exceptions are not displayed in the UI.

## Automated validation

- `python -m pytest -q`: **38 passed**.
- Python compilation: passed.
- JavaScript ES-module syntax checks for `app.js`, `firebase-ai.js`, `local-store.js`, `preferences.js`, and `landing.js`: passed.
- CSS parsing: **397 top-level rules, zero syntax errors**.
- HTML checks: no duplicate IDs, no eyebrow labels, and no footer elements in application, landing, 404, or 500 templates.
- Landing-page checks confirm one interactive product preview, no fake social proof, and no separate practice-product cards.
- Settings checks confirm the theme and font-size controls exist, persist locally, and do not expose implementation details.
- IndexedDB reconnection and user-facing error mapping checks: passed.

## Browser-rendered UX checks

The HTML and stylesheet were rendered in headless Chromium using the application DOM and the practice-mode/settings interaction logic.

- Landing preview mode switches between the prepared-answer and spontaneous prompts, including the displayed duration.
- Responsive layout checks at 1440px, 768px, and 390px reported no horizontal overflow.
- Structured practice is selected and visible by default. Switching to Hot Take updates the selected tab, ARIA state, keyboard tab stop, and visible panel together. The transition was allowed to settle before visual capture.
- The practice panel reports `outline-style: none`; keyboard-focus styling remains on actual controls.
- Settings changes the page theme and increases body text from 16px to 20px when Large is selected.

## External verification still required

These checks require the client's configured environment and supported device: live Firebase AI Logic requests; actual Gemini Nano model availability and on-device inference; cloud fallback; microphone permission and local speech recognition; screen-reader and keyboard testing with assistive technology; and deployment to Vercel. Browser-rendered layout checks do not replace production-device acceptance testing.
