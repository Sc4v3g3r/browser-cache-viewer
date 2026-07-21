"""Browser Cache Viewer — Flask web UI for parsing Chrome & Firefox caches.

Configuration is read from environment variables (see .env.example):
    CHROME_CACHE_DIR   Default Chrome/Chromium Simple Cache directory to show.
    FIREFOX_CACHE_BASE Base Firefox profiles directory to auto-scan for cache2.
    HOST               Interface to bind (default 127.0.0.1).
    PORT               Port to bind (default 5000).
    FLASK_DEBUG        Set to "1"/"true" to enable Flask debug mode (default off).
    MAX_UPLOAD_MB      Max upload size for the .zip endpoint (default 500).
"""
import os
import io
import traceback
import tempfile
import shutil
import zipfile

from flask import Flask, jsonify, request, send_file, render_template

from cache_parser import CacheParser

app = Flask(__name__)

MAX_UPLOAD_MB = int(os.environ.get("MAX_UPLOAD_MB", "500"))
app.config["MAX_CONTENT_LENGTH"] = MAX_UPLOAD_MB * 1024 * 1024

UPLOAD_TEMP_DIR = os.path.join(tempfile.gettempdir(), "cache_viewer_uploads")

# Sensible defaults; override with environment variables for your own machine.
DEFAULT_CHROME_DIR = os.environ.get(
    "CHROME_CACHE_DIR",
    os.path.expanduser("~/.cache/chromium/Default/Cache/Cache_Data"),
)
FIREFOX_CACHE_BASE = os.environ.get(
    "FIREFOX_CACHE_BASE",
    os.path.expanduser("~/.cache/mozilla/firefox/"),
)


def _default_firefox_dir():
    """Return the first Firefox profile cache2/entries dir, if one exists."""
    if os.path.isdir(FIREFOX_CACHE_BASE):
        for dirname in os.listdir(FIREFOX_CACHE_BASE):
            cache_path = os.path.join(FIREFOX_CACHE_BASE, dirname, "cache2", "entries")
            if os.path.exists(cache_path):
                return cache_path
    return os.path.join(FIREFOX_CACHE_BASE, "unknown.default", "cache2", "entries")


@app.route("/")
def index():
    return render_template(
        "index.html",
        chrome_dir=DEFAULT_CHROME_DIR,
        firefox_dir=_default_firefox_dir(),
    )


@app.route("/api/cache/list")
def list_cache():
    cache_dir = request.args.get("dir", DEFAULT_CHROME_DIR)
    try:
        parser = CacheParser(cache_dir)
        entries = parser.get_entries_metadata()
        # Sort entries by request time descending.
        entries.sort(key=lambda x: x.get("request_time") or "", reverse=True)
        return jsonify({"success": True, "entries": entries})
    except Exception as e:
        traceback.print_exc()
        return jsonify({"success": False, "error": str(e)}), 400


@app.route("/api/cache/view/<string:item_id>")
def view_cache(item_id):
    cache_dir = request.args.get("dir", DEFAULT_CHROME_DIR)
    try:
        parser = CacheParser(cache_dir)
        entry_data = parser.get_entry_data(item_id)
        if not entry_data:
            return "Cache entry not found or no payload.", 404

        payload = entry_data["payload"]
        if not payload:
            return "Cache entry has no payload.", 404

        content_type = entry_data.get("content_type", "application/octet-stream")

        # Determine a download name from the URL, with a generic fallback.
        url = entry_data.get("url", "")
        filename = url.split("/")[-1].split("?")[0] if url else "cached_file"
        if not filename:
            filename = "cached_file"

        return send_file(
            io.BytesIO(payload),
            mimetype=content_type,
            as_attachment=False,
            download_name=filename,
        )
    except Exception as e:
        traceback.print_exc()
        return str(e), 500


@app.route("/api/cache/upload", methods=["POST"])
def upload_cache():
    if "file" not in request.files:
        return jsonify({"success": False, "error": "No file uploaded."}), 400

    uploaded = request.files["file"]
    if not uploaded.filename or not uploaded.filename.lower().endswith(".zip"):
        return jsonify({"success": False, "error": "Please upload a .zip file."}), 400

    try:
        # Clean previous uploads.
        if os.path.exists(UPLOAD_TEMP_DIR):
            shutil.rmtree(UPLOAD_TEMP_DIR)
        os.makedirs(UPLOAD_TEMP_DIR, exist_ok=True)

        zip_path = os.path.join(UPLOAD_TEMP_DIR, "upload.zip")
        uploaded.save(zip_path)

        extract_dir = os.path.join(UPLOAD_TEMP_DIR, "extracted")
        _safe_extract(zip_path, extract_dir)

        # Find the actual cache directory inside the extracted content.
        cache_path = _find_cache_dir(extract_dir)
        if not cache_path:
            return (
                jsonify(
                    {
                        "success": False,
                        "error": "Could not find valid Chrome or Firefox cache files in the ZIP.",
                    }
                ),
                400,
            )

        return jsonify({"success": True, "cache_dir": cache_path})
    except zipfile.BadZipFile:
        return jsonify({"success": False, "error": "Invalid ZIP file."}), 400
    except Exception as e:
        traceback.print_exc()
        return jsonify({"success": False, "error": str(e)}), 500


def _safe_extract(zip_path, extract_dir):
    """Extract a zip while guarding against path-traversal (zip-slip)."""
    os.makedirs(extract_dir, exist_ok=True)
    dest_root = os.path.realpath(extract_dir)
    with zipfile.ZipFile(zip_path, "r") as zf:
        for member in zf.namelist():
            target = os.path.realpath(os.path.join(extract_dir, member))
            if not (target == dest_root or target.startswith(dest_root + os.sep)):
                raise ValueError(f"Unsafe path in archive: {member}")
        zf.extractall(extract_dir)


def _find_cache_dir(base_dir):
    """Walk the extracted directory to find the actual cache data folder."""
    try:
        CacheParser(base_dir)
        return base_dir
    except Exception:
        pass

    for root, _dirs, _files in os.walk(base_dir):
        try:
            CacheParser(root)
            return root
        except Exception:
            continue
    return None


if __name__ == "__main__":
    host = os.environ.get("HOST", "127.0.0.1")
    port = int(os.environ.get("PORT", "5000"))
    debug = os.environ.get("FLASK_DEBUG", "").lower() in ("1", "true", "yes")
    app.run(host=host, port=port, debug=debug)
