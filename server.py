from flask import Flask, request, send_file, jsonify
from flask_cors import CORS
import yt_dlp
import os
import uuid
from pathlib import Path

app = Flask(__name__)
CORS(app)

DOWNLOAD_DIR = "/tmp/ytmp3"
Path(DOWNLOAD_DIR).mkdir(parents=True, exist_ok=True)
COOKIES_FILE = "/opt/render/project/src/cookies.txt"


@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok"})


@app.route("/info", methods=["POST"])
def get_info():
    data = request.get_json()
    url = data.get("url", "").strip()
    if not url:
        return jsonify({"error": "No URL provided"}), 400
    try:
        ydl_opts = {
            "quiet": True,
            "no_warnings": True,
            "cookiefile": COOKIES_FILE,
            "skip_download": True,
            "format": "bestaudio/best",
            "ignoreerrors": True,
            "noplaylist": False,
        }
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)

        if info is None:
            return jsonify({"error": "Could not fetch video info"}), 500

        is_playlist = info.get("_type") == "playlist"
        if is_playlist:
            entries = [e for e in info.get("entries", []) if e]
            return jsonify({
                "is_playlist": True,
                "title": info.get("title", "Playlist"),
                "count": len(entries),
                "entries": [{
                    "title": e.get("title", "Unknown"),
                    "thumbnail": e.get("thumbnail", ""),
                    "duration": e.get("duration", 0),
                    "url": e.get("webpage_url") or e.get("url", ""),
                    "uploader": e.get("uploader", "Unknown"),
                } for e in entries[:50]],
            })
        else:
            return jsonify({
                "is_playlist": False,
                "title": info.get("title", "Unknown"),
                "thumbnail": info.get("thumbnail", ""),
                "duration": info.get("duration", 0),
                "uploader": info.get("uploader", "Unknown"),
                "url": url,
            })
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/download", methods=["POST"])
def download():
    data = request.get_json()
    url = data.get("url", "").strip()
    if not url:
        return jsonify({"error": "No URL provided"}), 400

    file_id = str(uuid.uuid4())
    output_template = os.path.join(DOWNLOAD_DIR, f"{file_id}.%(ext)s")

    try:
        ydl_opts = {
            "quiet": True,
            "no_warnings": True,
            "cookiefile": COOKIES_FILE,
            "outtmpl": output_template,
            "format": "bestaudio/best",
            "postprocessors": [{
                "key": "FFmpegExtractAudio",
                "preferredcodec": "mp3",
                "preferredquality": "320",
            }],
        }
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            title = info.get("title", "audio") if info else "audio"

        mp3_path = os.path.join(DOWNLOAD_DIR, f"{file_id}.mp3")
        if not os.path.exists(mp3_path):
            for f in os.listdir(DOWNLOAD_DIR):
                if f.startswith(file_id):
                    mp3_path = os.path.join(DOWNLOAD_DIR, f)
                    break

        safe_title = "".join(c for c in title if c.isalnum() or c in " -_").strip()
        return send_file(
            mp3_path,
            as_attachment=True,
            download_name=f"{safe_title or 'audio'}.mp3",
            mimetype="audio/mpeg",
        )
    except Exception as e:
        return jsonify({"error": str(e)}), 500


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)