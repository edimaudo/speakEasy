from html.parser import HTMLParser
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]


def test_python_first_structure_has_no_js_build_stack():
    forbidden = ["package.json", "tsconfig.json", "vite.config.js", "vite.config.ts", "app.py"]
    for path in forbidden:
        assert not (ROOT / path).exists(), path
    assert (ROOT / "main.py").exists()
    assert (ROOT / "requirements.txt").exists()
    assert (ROOT / "vercel.json").exists()
    assert (ROOT / "templates" / "landing.html").exists()
    assert (ROOT / "templates" / "index.html").exists()


def test_no_server_database_or_persistent_storage_dependency_exists():
    requirements = (ROOT / "requirements.txt").read_text().lower()
    forbidden_dependencies = ("sqlalchemy", "psycopg", "asyncpg", "databases", "firebase-admin")
    assert not any(name in requirements for name in forbidden_dependencies)
    for relative_path in ("app/database.py", "app/models.py", "app/security.py", "data"):
        assert not (ROOT / relative_path).exists(), relative_path
    source = (ROOT / "main.py").read_text().lower()
    assert "sqlalchemy" not in source
    assert "database_url" not in source
    assert "create_database" not in source
    assert not list(ROOT.rglob("*.sqlite"))
    assert not list(ROOT.rglob("*.sqlite3"))
    assert not list(ROOT.rglob("*.db"))


def test_browser_local_store_owns_history_and_usage_not_vercel():
    store = (ROOT / "public" / "static" / "js" / "local-store.js").read_text()
    app_js = (ROOT / "public" / "static" / "js" / "app.js").read_text()
    assert "indexedDB.open" in store
    assert "expiresAt" in store
    assert "listSessions" in app_js
    assert '"/api/sessions' not in app_js
    assert '"/api/usage' not in app_js


def test_no_other_firebase_products_or_admin_sdks_are_installed():
    requirements = (ROOT / "requirements.txt").read_text().lower()
    assert "firebase-admin" not in requirements
    assert "firebase" not in requirements
    js_sources = "\n".join(path.read_text() for path in (ROOT / "public" / "static" / "js").glob("*.js"))
    assert "firebase-auth.js" not in js_sources
    assert "firebase-firestore.js" not in js_sources
    assert "firebase-storage.js" not in js_sources
    assert "firebase-ai.js" in js_sources


def test_templates_and_static_assets_exist():
    assert (ROOT / "public" / "static" / "css" / "styles.css").exists()
    for filename in ("firebase-ai.js", "app.js", "local-store.js", "preferences.js", "landing.js"):
        assert (ROOT / "public" / "static" / "js" / filename).exists()


class _IdParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.ids = set()

    def handle_starttag(self, tag, attrs):
        values = dict(attrs)
        if values.get("id"):
            self.ids.add(values["id"])


def test_all_literal_javascript_id_selectors_exist_in_template():
    parser = _IdParser()
    parser.feed((ROOT / "templates" / "index.html").read_text())
    js = (ROOT / "public" / "static" / "js" / "app.js").read_text()
    selectors = set(re.findall(r'\$\("#([a-zA-Z0-9_-]+)"\)', js))
    selectors.update(re.findall(r'\$\(`#([a-zA-Z0-9_-]+)`\)', js))
    assert selectors, "Expected browser code to use explicit ID selectors."
    assert selectors <= parser.ids, f"Selectors missing from HTML: {sorted(selectors - parser.ids)}"


def test_html_static_asset_paths_map_to_public_directory(client):
    landing = client.get("/")
    app = client.get("/app")
    assert landing.status_code == 200
    assert app.status_code == 200
    assert 'href="/static/css/styles.css"' in landing.text
    assert 'src="/static/js/landing.js"' in landing.text
    assert 'src="/static/js/app.js"' in app.text

    css = client.get("/static/css/styles.css")
    app_js = client.get("/static/js/app.js")
    ai_js = client.get("/static/js/firebase-ai.js")
    store_js = client.get("/static/js/local-store.js")
    prefs_js = client.get("/static/js/preferences.js")
    landing_js = client.get("/static/js/landing.js")
    assert css.status_code == 200 and "text/css" in css.headers["content-type"]
    assert app_js.status_code == 200 and "javascript" in app_js.headers["content-type"]
    assert ai_js.status_code == 200 and "firebase-ai.js" in ai_js.text
    assert store_js.status_code == 200 and "indexedDB.open" in store_js.text
    assert prefs_js.status_code == 200 and "setupAppearanceSettings" in prefs_js.text
    assert landing_js.status_code == 200 and "data-demo-mode" in landing_js.text


def test_no_typescript_or_node_frontend_build_files_exist():
    forbidden_names = {"package.json", "package-lock.json", "tsconfig.json", "vite.config.js", "vite.config.ts"}
    files = [path for path in ROOT.rglob("*") if path.is_file() and not any(part.startswith(".") for part in path.relative_to(ROOT).parts)]
    assert not [path.relative_to(ROOT).as_posix() for path in files if path.name in forbidden_names]
    assert not [path.relative_to(ROOT).as_posix() for path in files if path.suffix in {".ts", ".tsx"}]


def test_hybrid_ai_modes_and_inference_source_are_explicit():
    ai = (ROOT / "public" / "static" / "js" / "firebase-ai.js").read_text()
    assert "InferenceMode.PREFER_ON_DEVICE" in ai
    assert "InferenceMode.PREFER_IN_CLOUD" in ai
    assert "result?.response?.inferenceSource" in ai
    assert "initializeDeviceModel" in ai
    assert "AgentPlatformBackend" in ai


def test_microphone_is_local_and_no_audio_blob_or_recorder_is_used():
    app_js = (ROOT / "public" / "static" / "js" / "app.js").read_text()
    assert "recognition.processLocally = true" in app_js
    assert "getUserMedia" in app_js
    assert "createMediaStreamSource" in app_js
    assert "MediaRecorder" not in app_js
    assert "new Blob" not in app_js


def test_custom_error_templates_and_shared_error_styles_exist():
    for page in ("404.html", "500.html"):
        markup = (ROOT / "templates" / page).read_text()
        assert 'href="/static/css/styles.css"' in markup
        assert 'href="/"' in markup
        assert 'class="error-page-shell"' in markup
    css = (ROOT / "public" / "static" / "css" / "styles.css").read_text()
    for selector in (".error-page-shell", ".error-page-main", ".error-code", ".error-home-button"):
        assert selector in css


def test_python_dotenv_is_local_optional_dependency():
    root_source = (ROOT / "main.py").read_text()
    requirements = (ROOT / "requirements.txt").read_text().lower()
    assert "python-dotenv" in requirements
    assert "except ModuleNotFoundError" in root_source
    assert "load_dotenv is not None" in root_source


def test_no_duplicate_dependency_manifest():
    assert (ROOT / "requirements.txt").exists()
    assert not (ROOT / "pyproject.toml").exists()


def test_vercel_has_no_cron_or_database_configuration():
    vercel = (ROOT / "vercel.json").read_text().lower()
    assert "cron" not in vercel
    env_example = (ROOT / ".env.example").read_text().lower()
    assert "database_url" not in env_example
    assert "postgres" not in env_example


def test_main_interface_has_no_eyebrows_footers_or_brand_mark():
    for page in ("index.html", "404.html", "500.html"):
        markup = (ROOT / "templates" / page).read_text().lower()
        assert "eyebrow" not in markup
        assert "<footer" not in markup
        assert "brand-mark" not in markup
    css = (ROOT / "public" / "static" / "css" / "styles.css").read_text().lower()
    assert ".eyebrow" not in css
    assert ".footer" not in css


def test_landing_page_is_concise_and_uses_only_prd_content(client):
    landing = (ROOT / "templates" / "landing.html").read_text()
    assert "Practise speaking." in landing
    assert "Make your point." in landing
    assert "60-second answers" in landing
    assert "90-second position" in landing
    assert "Get a score, one line to fix and a stronger opening" in landing
    assert 'class="landing-demo"' in landing
    assert 'role="tablist" aria-label="Practice format"' in landing
    assert 'data-demo-mode="structured"' in landing
    assert 'data-demo-mode="spontaneous"' in landing
    assert 'href="/app"' in landing
    assert "Start practising" in landing
    assert "social proof" not in landing.lower()
    assert "pricing" not in landing.lower()
    assert "testimonial" not in landing.lower()
    assert "Hot Take Arena" not in landing
    assert "Firebase" not in landing
    assert "Gemini" not in landing
    assert "eyebrow" not in landing.lower()
    assert "<footer" not in landing.lower()
    assert "What you can practise" not in landing
    assert "landing-feature" not in landing
    assert landing.count("<section") == 1
    assert "Choose a prompt" not in landing
    assert "Speak under the timer" not in landing
    assert "Fix one thing and retry" not in landing

    application = (ROOT / "templates" / "index.html").read_text()
    assert 'id="practice-workspace"' in application
    assert 'role="tablist" aria-label="Practice format"' in application
    assert 'data-practice-mode="structured"' in application
    assert 'data-practice-mode="hot-take"' in application
    assert 'data-practice-panel="structured"' in application
    assert 'data-practice-panel="hot-take" hidden' in application
    assert 'structured-layout' in application
    assert 'hot-take-layout' in application
    assert "Hot Take Arena" not in application
    assert 'data-view="arena"' not in application
    assert 'id="question-list"' in application
    assert 'id="hot-take-result"' in application
    assert 'id="session-panel"' in application
    assert 'id="scorecard-panel"' in application
    assert 'id="settings-dialog"' in application

    app_js = (ROOT / "public" / "static" / "js" / "app.js").read_text()
    assert 'function setPracticeMode(mode, moveFocus = false)' in app_js
    assert 'setPracticeMode("structured")' in app_js
    assert 'setPracticeMode(tabs[next].dataset.practiceMode, true)' in app_js
    assert '$("#hot-take-empty").hidden = true;' in app_js
    assert 'view === "arena"' not in app_js

    landing_js = (ROOT / "public" / "static" / "js" / "landing.js").read_text()
    assert "demoModes" in landing_js
    assert "aria-selected" in landing_js
    assert '"#demo-prompt-text"' in landing_js


def test_application_uses_a_speaking_tool_layout_not_chat_or_generic_ai_cards():
    markup = (ROOT / "templates" / "index.html").read_text().lower()
    css = (ROOT / "public" / "static" / "css" / "styles.css").read_text().lower()
    assert "chat bubble" not in markup
    assert "ask ai" not in markup
    assert "chat input" not in markup
    assert 'structured-layout' in markup
    assert 'questions-column' in markup
    assert 'hot-take-layout' in markup
    assert "--accent: #b34e34" in css
    assert "#7657d6" not in css and "#ae9af4" not in css
    assert "linear-gradient(" not in css
    assert ".structured-layout, .hot-take-layout { display: grid;" in css
    assert ".practice-workspace { width: 100%; margin: 0 0 65px; }" in css
    assert ".session-panel, .scorecard-panel" in css



def test_visual_direction_is_direct_not_chatgpt_or_card_based():
    css = (ROOT / "public" / "static" / "css" / "styles.css").read_text().lower()
    app = (ROOT / "templates" / "index.html").read_text().lower()
    landing = (ROOT / "templates" / "landing.html").read_text().lower()

    assert "--accent: #b34e34" in css
    assert "#7657d6" not in css and "#ae9af4" not in css
    assert "linear-gradient(" not in css
    assert "chat bubble" not in app and "ask ai" not in app and "chat input" not in app
    workspace_rule = css.split(".practice-workspace {", 1)[1].split("}", 1)[0]
    panel_rule = css.split(".practice-mode-panel {", 1)[1].split("}", 1)[0]
    assert "box-shadow" not in workspace_rule and "box-shadow: none" in panel_rule
    assert ".practice-workspace { width: 100%; margin: 0 0 65px; }" in css
    assert ".structured-layout, .hot-take-layout { display: grid;" in css
    assert ".practice-mode-panel { min-width: 0; padding: 38px 0 30px; outline: none; box-shadow: none; }" in css
    assert "border-radius: 999px" not in css
    assert "landing-final-cta" not in landing
    assert "landing-practice" not in landing
    assert landing.count("start practising") == 1
    assert "60-second answers" in landing and "90-second position" in landing


def test_settings_has_theme_and_font_size_controls_without_implementation_terms():
    application = (ROOT / "templates" / "index.html").read_text()
    dialog = application[application.index('<dialog id="settings-dialog"'):application.index('<div id="toast"')]
    for label in ('Light', 'Dark', 'Small', 'Medium', 'Large'):
        assert f">{label}</button>" in dialog
    for implementation_term in ('Firebase', 'IndexedDB', 'Gemini', 'Gemini Nano'):
        assert implementation_term.lower() not in dialog.lower()
    preferences = (ROOT / "public" / "static" / "js" / "preferences.js").read_text()
    assert 'localStorage.setItem(STORAGE_KEY' in preferences
    assert 'data-theme-choice' in preferences
    assert 'data-font-size-choice' in preferences
    css = (ROOT / "public" / "static" / "css" / "styles.css").read_text()
    assert ':root[data-theme="dark"]' in css
    assert ':root[data-font-size="small"]' in css
    assert ':root[data-font-size="medium"]' in css
    assert ':root[data-font-size="large"]' in css


def test_section_focus_outline_is_removed_but_control_focus_is_retained():
    css = (ROOT / "public" / "static" / "css" / "styles.css").read_text()
    assert ':where(a, button, input, textarea, select, summary):focus-visible { outline: 2px solid var(--focus-ring); outline-offset: 3px; }' in css
    assert ':where(main, section, article, [role="tabpanel"], .view):focus-visible { outline: none; box-shadow: none; }' in css


def test_removed_landing_copy_and_ai_setup_banner():
    markup = (ROOT / "templates" / "index.html").read_text()
    app_js = (ROOT / "public" / "static" / "js" / "app.js").read_text()
    firebase_ai = (ROOT / "public" / "static" / "js" / "firebase-ai.js").read_text()
    assert "60 seconds to sharpen" not in markup.lower()
    assert "90 seconds to take a stand" not in markup.lower()
    assert "ai setup required" not in markup.lower()
    assert "ai setup required" not in app_js.lower()
    assert 'id="ai-status" class="status-pill" role="status" aria-live="polite" hidden' in markup
    assert "Add Firebase AI Logic configuration" not in firebase_ai


def test_settings_action_is_visibly_labelled_and_not_footer_dependent():
    markup = (ROOT / "templates" / "index.html").read_text()
    assert '<button id="settings-toggle" class="settings-button"' in markup
    assert '>Settings</button>' in markup
    assert 'id="privacy-open"' not in markup


def test_indexeddb_connection_is_invalidated_and_reopened_when_closing():
    source = (ROOT / "public" / "static" / "js" / "local-store.js").read_text()
    assert "db.onversionchange" in source
    assert "db.onclose" in source
    assert "async function createTransaction" in source
    assert "database connection is closing" in source
    assert "Local history briefly disconnected" in source


def test_browser_never_displays_raw_indexeddb_connection_closing_error():
    source = (ROOT / "public" / "static" / "js" / "app.js").read_text()
    assert "function friendlyMessage(message)" in source
    assert "Local history was interrupted. Your response is still on screen; please try again." in source


def test_error_pages_follow_the_same_brand_and_no_conversation_copy():
    for page in ("404.html", "500.html"):
        markup = (ROOT / "templates" / page).read_text()
        assert "family=Inter" in markup
        assert 'class="brand" href="/" aria-label="SpeakEasy home">SpeakEasy</a>' in markup
        assert "brand-period" not in markup
        assert "conversation" not in markup.lower()
        assert "error-page-footnote" not in markup


def test_structured_practice_has_context_inputs_for_each_goal():
    markup = (ROOT / "templates" / "index.html").read_text()
    app_js = (ROOT / "public" / "static" / "js" / "app.js").read_text()
    ai_js = (ROOT / "public" / "static" / "js" / "firebase-ai.js").read_text()
    assert 'id="job-description"' in markup
    assert 'id="presentation-context"' in markup
    assert 'id="everyday-context"' in markup
    for identifier in ("job-description", "presentation-context", "everyday-context"):
        assert f'<label for="{identifier}"' in markup
    assert '$("#presentation-context").value' in app_js
    assert '$("#everyday-context").value' in app_js
    assert "<presentation_context>" in ai_js
    assert "<speaking_context>" in ai_js


def test_question_heading_does_not_expose_browser_session_allowance():
    markup = (ROOT / "templates" / "index.html").read_text()
    app_js = (ROOT / "public" / "static" / "js" / "app.js").read_text()
    assert "Choose a question to practise." in markup
    assert "free sessions left today" not in markup.lower()
    assert "free sessions left today" not in app_js.lower()
    assert "of ${usage.limit}" not in app_js


def test_ai_configuration_errors_are_user_friendly():
    ai_js = (ROOT / "public" / "static" / "js" / "firebase-ai.js").read_text()
    assert "AI coaching is unavailable right now. Check the Firebase AI Logic configuration" not in ai_js
    assert "We could not prepare speaking practice right now." in ai_js
    assert "We could not create your feedback right now." in ai_js


def test_accessibility_landmarks_labels_and_keyboard_skip_links():
    landing = (ROOT / "templates" / "landing.html").read_text()
    app = (ROOT / "templates" / "index.html").read_text()
    css = (ROOT / "public" / "static" / "css" / "styles.css").read_text()
    landing_js = (ROOT / "public" / "static" / "js" / "landing.js").read_text()
    for markup in (landing, app):
        assert 'class="skip-link" href="#main-content"' in markup
        assert 'id="main-content"' in markup
    for identifier in ("job-description", "presentation-context", "everyday-context", "hot-category", "custom-topic", "live-transcript"):
        assert f'for="{identifier}"' in app
    assert 'aria-live="polite"' in app
    assert 'role="progressbar"' not in app  # Metrics are populated dynamically with labels and values.
    assert 'role="progressbar" aria-label="${label}"' in (ROOT / "public" / "static" / "js" / "app.js").read_text()
    assert 'ArrowRight' in landing_js and 'ArrowLeft' in landing_js
    assert ':focus-visible' in css and '.skip-link:focus' in css


def test_wcag_aa_core_palette_contrast_and_control_boundaries():
    css = (ROOT / "public" / "static" / "css" / "styles.css").read_text()
    assert "--muted-2: #5f6b63" in css
    assert "--field-border: #747f76" in css
    assert "--field-border: #819187" in css
    assert ".skip-link" in css
    assert "min-height: 46px" in css
    assert "min-height: 36px" in css


def test_all_landing_process_steps_are_removed():
    landing = (ROOT / "templates" / "landing.html").read_text()
    css = (ROOT / "public" / "static" / "css" / "styles.css").read_text()
    assert "landing-loop" not in landing
    assert "Choose a prompt" not in landing
    assert "Speak under the timer" not in landing
    assert "Fix one thing and retry" not in landing
    assert ".landing-loop" not in css


def _contrast_ratio(hex_a, hex_b):
    def luminance(value):
        value = value.lstrip("#")
        rgb = [int(value[index:index + 2], 16) / 255 for index in (0, 2, 4)]
        linear = [channel / 12.92 if channel <= 0.04045 else ((channel + 0.055) / 1.055) ** 2.4 for channel in rgb]
        return 0.2126 * linear[0] + 0.7152 * linear[1] + 0.0722 * linear[2]

    first, second = sorted((luminance(hex_a), luminance(hex_b)), reverse=True)
    return (first + 0.05) / (second + 0.05)


def test_text_and_ui_boundaries_meet_wcag_aa_core_contrast_thresholds():
    css = (ROOT / "public" / "static" / "css" / "styles.css").read_text()
    light = {
        "ink": "#202823", "muted": "#5f6b63", "muted_2": "#5f6b63",
        "paper": "#f7f6f1", "surface": "#fbfaf6", "surface_2": "#eeede6",
        "field": "#fbfaf6", "field_border": "#747f76", "focus": "#245b43",
    }
    dark = {
        "ink": "#edf0eb", "muted": "#b4bcb5", "muted_2": "#929b93",
        "paper": "#171d19", "surface": "#1e2721", "surface_2": "#27312a",
        "field": "#1b241e", "field_border": "#819187", "focus": "#a4d0ad",
    }
    for palette in (light, dark):
        for foreground, background in (("ink", "paper"), ("ink", "surface"), ("muted", "paper"),
                                       ("muted", "surface"), ("muted", "surface_2"),
                                       ("muted_2", "paper"), ("muted_2", "surface_2"),
                                       ("muted_2", "field")):
            assert _contrast_ratio(palette[foreground], palette[background]) >= 4.5, (foreground, background, palette)
        assert _contrast_ratio(palette["field_border"], palette["field"]) >= 3
        assert _contrast_ratio(palette["focus"], palette["paper"]) >= 3
    assert "--muted: #5f6b63" in css
