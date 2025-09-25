import os
import sys
import json
import subprocess
from flask import Flask, render_template, request, jsonify, Response, send_from_directory
from urllib.parse import urlparse

# Import the unified downloader functions
from youtube_downloader import get_media_details, download_media

app = Flask(__name__)

# --- Helper Functions ---
def is_youtube_url(url):
    parsed_url = urlparse(url)
    return "youtube.com" in parsed_url.netloc or "youtu.be" in parsed_url.netloc

def is_instagram_url(url):
    parsed_url = urlparse(url)
    return "instagram.com" in parsed_url.netloc

def is_pinterest_url(url):
    parsed_url = urlparse(url)
    return "pinterest." in parsed_url.netloc or "pin.it" in parsed_url.netloc


# --- Flask Routes ---
@app.route('/')
def index():
    return render_template('download.html')

@app.route('/get-video-info', methods=['POST'])
def get_video_info():
    url = request.json.get('url')
    if not url:
        return jsonify({"error": "URL is required."}), 400

    if not (is_youtube_url(url) or is_instagram_url(url) or is_pinterest_url(url)):
        return jsonify({"error": "Invalid URL. Please enter a valid YouTube, Instagram, or Pinterest URL."}), 400

    print(f"Fetching details for URL: {url}")
    details = get_media_details(url)
    
    if "error" in details:
        return jsonify(details), 400
    
    return jsonify(details)


@app.route('/download', methods=['GET'])
def download():
    url = request.args.get('url')
    download_type = request.args.get('type', 'video')
    
    if not url:
        return "Error: URL parameter is missing.", 400

    return download_media(url, download_type)

@app.route('/get-file/<filename>')
def get_file(filename):
    """
    Serves the downloaded file to the user's browser.
    """
    downloads_dir = '/app/downloads' if os.path.exists('/app') else 'downloads'
    safe_path = os.path.join(downloads_dir, filename)
    if not os.path.isfile(safe_path):
        return "File not found.", 404

    return send_from_directory(downloads_dir, filename, as_attachment=True)


# --- Main Execution (for local development) ---
def check_command(command):
    try:
        subprocess.run([command, '--version'], check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        return True
    except (subprocess.CalledProcessError, FileNotFoundError):
        return False

if __name__ == '__main__':
    if not check_command('yt-dlp'):
        print("❌ Fatal Error: 'yt-dlp' not found. Please run: pip install yt-dlp")
        sys.exit(1)
    if not check_command('ffmpeg'):
        print("❌ Warning: 'ffmpeg' not found. Downloads for high-quality formats might fail.")

    print("✅ yt-dlp and ffmpeg checks passed.")
    print(f"🌍 Starting Flask web server at http://127.0.0.1:5123")
    app.run(host='0.0.0.0', port=5123, debug=True)

