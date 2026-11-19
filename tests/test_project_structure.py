from pathlib import Path
from html.parser import HTMLParser
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
    assert (ROOT / "public" / "static" / "js" / "firebase-ai.js").exists()
    assert (ROOT / "public" / "static" / "js" / "app.js").exists()


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


def test_browser_firebase_imports_are_limited_to_ai_logic_and_required_bootstrap():
    js = (ROOT / "public" / "static" / "js" / "firebase-ai.js").read_text()
    assert "firebase-app.js" in js
    assert "firebase-ai.js" in js
    assert "firebase-app-check.js" in js
    assert "firebase-auth.js" not in js
    assert "firebase-firestore.js" not in js
    assert "firebase-storage.js" not in js
    assert "firebase-admin" not in js.lower()


def test_html_static_asset_paths_map_to_public_directory(client):
    home = client.get("/")
    assert home.status_code == 200
    assert 'href="/static/css/styles.css"' in home.text
    assert 'src="/static/js/app.js"' in home.text

    css = client.get("/static/css/styles.css")
    app_js = client.get("/static/js/app.js")
    ai_js = client.get("/static/js/firebase-ai.js")
    assert css.status_code == 200 and "text/css" in css.headers["content-type"]
    assert app_js.status_code == 200 and "javascript" in app_js.headers["content-type"]
    assert ai_js.status_code == 200 and "firebase-ai.js" in ai_js.text


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
