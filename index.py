import os
import sys
from flask import Flask, render_template, request, jsonify, send_from_directory, send_file, after_this_request
from werkzeug.utils import secure_filename, safe_join
from youtube_downloader import get_media_details, download_media
from gevent.pywsgi import WSGIServer

app = Flask(__name__, static_url_path='/static')
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024 # 16 MB max request size

# --- Constants ---
DOWNLOADS_DIR = '/app/downloads' if os.path.exists('/app') else 'downloads'
if not os.path.exists(DOWNLOADS_DIR):
    os.makedirs(DOWNLOADS_DIR)

# --- Routes ---
@app.route('/')
def index():
    return render_template('download.html')

@app.route('/get-video-info', methods=['POST'])
def get_video_info_route():
    data = request.get_json()
    url = data.get('url')
    if not url:
        return jsonify({"error": "URL is required."}), 400
    details = get_media_details(url)
    if details.get("error"):
        return jsonify(details), 400
    return jsonify(details)

@app.route('/download')
def download_route():
    url = request.args.get('url')
    download_type = request.args.get('type', 'video')
    if not url:
        return "URL parameter is missing", 400
    return download_media(url, download_type)

@app.route('/get-file/<filename>')
def get_file(filename):
    """
    Serves a file for download and then deletes it from the server.
    This prevents the server's disk from filling up.
    Includes a fallback for mismatched extensions to fix "Not Found" errors.
    """
    safe_filename = secure_filename(filename)
    safe_path = safe_join(DOWNLOADS_DIR, safe_filename)
    
    # --- FIX: Check for the file, and if not found, try the alternative extension ---
    if not os.path.exists(safe_path):
        name, ext = os.path.splitext(safe_filename)
        if ext.lower() == '.mp3':
            alternative_path = safe_join(DOWNLOADS_DIR, name + '.mp4')
            if os.path.exists(alternative_path):
                safe_path = alternative_path
        elif ext.lower() == '.mp4':
            alternative_path = safe_join(DOWNLOADS_DIR, name + '.mp3')
            if os.path.exists(alternative_path):
                safe_path = alternative_path

    # If still not found after checking alternatives, return 404
    if not os.path.exists(safe_path):
        return "File not found.", 404

    @after_this_request
    def remove_file(response):
        try:
            os.remove(safe_path)
            print(f"Removed temporary file: {safe_path}")
        except Exception as error:
            print(f"Error removing file {safe_path}: {error}")
        return response
    
    return send_file(safe_path, as_attachment=True)

if __name__ == '__main__':
    print("🌍 Starting web server with gevent at http://127.0.0.1:5123")
    http_server = WSGIServer(('0.0.0.0', 5123), app)
    http_server.serve_forever()

