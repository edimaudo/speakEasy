# SpeakEasy — UX, accessibility and responsive validation

## Changes in this revision

- Removed the landing-page numbered process section.
- Removed daily browser session allowance copy from the question toolbar; the question area now says only “Choose a question to practise.”
- Added labelled context textareas for Presentation and Everyday Speaking. Interview retains its optional job-description textarea.
- Replaced technical AI setup errors with short, user-facing messages.
- Added skip links, accessible labels, live status announcements, keyboard-operated landing tabs, and accessible score metric progress values.
- Increased muted text contrast in both themes and strengthened field boundaries and focus indicators.
- Checked responsive reflow and settings controls across desktop, tablet and narrow mobile widths.

## Automated checks

- `python -m pytest -q`: 48 tests passed.
- Python compilation: passed.
- Browser JavaScript ES-module syntax checks: passed.
- CSS parsing: zero syntax errors.
- All visible form controls have accessible names.
- Keyboard focus styling is present on interactive elements and absent from content panels.
- Automated WCAG 2.2 AA core contrast checks: normal text >= 4.5:1; non-text field boundaries and focus indicators >= 3:1.

## Browser checks

Headless Chromium was used with the server-rendered HTML and inlined local assets to avoid blocked local-network navigation in the execution environment. Checks passed at 1440, 1024, 768, 560, 430, 390, 375 and 320 CSS-pixel widths for both landing and app pages, with no horizontal overflow. Small, medium and large text modes were also checked in both light and dark themes.

Interaction checks passed for landing tabs, the Practice-format tabs (including arrow-key navigation and associated panel visibility), goal-specific context fields and the values sent to the question generator, theme selection, font-size selection, and generic AI error messaging. The Hot Take panel was also checked at all responsive widths across both themes and all three font-size choices. The settings dialog was checked at 320px and larger widths, including vertical scrolling without horizontal overflow. The browser test uses mocked AI and local storage interfaces; it does not claim to verify live Gemini inference or microphone permissions.

## WCAG scope and remaining manual review

The implementation addresses WCAG 2.2 AA requirements for text and non-text contrast, keyboard operability, visible focus, labels and instructions, status messages, skip navigation, semantic landmarks, and reflow. Automated checks are not a formal accessibility certification. All tested controls have accessible names, interactive targets are at least 24×24 CSS pixels, visible keyboard focus uses a 2px outline with offset, and no content-panel outline is introduced. Before launch, complete manual screen-reader testing with NVDA/VoiceOver, full keyboard testing of every recording and scorecard state, and real-device zoom/reflow testing.

## Not verified in this environment

- Live Firebase AI Logic calls, Gemini Nano model readiness and cloud fallback.
- Real microphone capture and browser speech recognition.
- Screen-reader announcements across assistive technology/browser combinations.
- Vercel production deployment.
