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
    for filename in ("firebase-ai.js", "app.js", "local-store.js"):
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
    home = client.get("/")
    assert home.status_code == 200
    assert 'href="/static/css/styles.css"' in home.text
    assert 'src="/static/js/app.js"' in home.text

    css = client.get("/static/css/styles.css")
    app_js = client.get("/static/js/app.js")
    ai_js = client.get("/static/js/firebase-ai.js")
    store_js = client.get("/static/js/local-store.js")
    assert css.status_code == 200 and "text/css" in css.headers["content-type"]
    assert app_js.status_code == 200 and "javascript" in app_js.headers["content-type"]
    assert ai_js.status_code == 200 and "firebase-ai.js" in ai_js.text
    assert store_js.status_code == 200 and "indexedDB.open" in store_js.text


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


def test_landing_page_integrates_structured_practice_and_hot_takes():
    markup = (ROOT / "templates" / "index.html").read_text()
    assert 'id="view-practice"' in markup
    assert 'id="structured-practice"' in markup
    assert 'id="hot-takes"' in markup
    assert 'id="view-arena"' not in markup
    practice_start = markup.index('id="view-practice"')
    history_start = markup.index('id="view-history"')
    practice_hub = markup[practice_start:history_start]
    assert practice_hub.index('id="structured-practice"') < practice_hub.index('id="hot-takes"')
    app_js = (ROOT / "public" / "static" / "js" / "app.js").read_text()
    assert 'view === "arena"' in app_js
    assert 'scrollIntoView' in app_js


def test_removed_landing_copy_and_ai_setup_banner():
    markup = (ROOT / "templates" / "index.html").read_text()
    app_js = (ROOT / "public" / "static" / "js" / "app.js").read_text()
    firebase_ai = (ROOT / "public" / "static" / "js" / "firebase-ai.js").read_text()
    assert "60 seconds to sharpen" not in markup.lower()
    assert "90 seconds to take a stand" not in markup.lower()
    assert "ai setup required" not in markup.lower()
    assert "ai setup required" not in app_js.lower()
    assert 'id="ai-status" class="status-pill" hidden' in markup
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
