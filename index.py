import os
import subprocess
import sys
import json
import re
import threading
import time
import uuid
from datetime import datetime
from flask import Flask, request, render_template, send_from_directory, jsonify, Response

# --- Flask App Setup ---
app = Flask(__name__)
app.secret_key = os.urandom(24)

# --- Configuration & State Management ---
DOWNLOAD_FOLDER = os.path.join(os.getcwd(), "downloads")
if not os.path.exists(DOWNLOAD_FOLDER):
    os.makedirs(DOWNLOAD_FOLDER)

# A thread-safe dictionary to store the state of concurrent downloads
tasks = {}

# --- Helper Functions ---
def check_yt_dlp():
    """Checks if yt-dlp is installed."""
    try:
        subprocess.run(['yt-dlp', '--version'], check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        return True
    except (subprocess.CalledProcessError, FileNotFoundError):
        return False

def format_number(num):
    """Formats a number into a human-readable string with commas."""
    if num is None:
        return "N/A"
    return f"{num:,}"

def format_date(date_str):
    """Formats a YYYYMMDD date string to 'Month Day, Year'."""
    if date_str is None:
        return "N/A"
    try:
        dt_obj = datetime.strptime(date_str, '%Y%m%d')
        return dt_obj.strftime('%B %d, %Y')
    except (ValueError, TypeError):
        return date_str

def download_thread(task_id, video_url, download_type):
    """The function that runs in a separate thread to handle the download."""
    try:
        tasks[task_id] = {'status': 'fetching_info', 'progress': 0, 'details': 'Fetching video details...'}
        info_proc = subprocess.run(
            ['yt-dlp', '--get-title', '--no-warnings', video_url],
            capture_output=True, text=True, check=True, encoding='utf-8'
        )
        video_title = info_proc.stdout.strip()
        safe_title = "".join([c for c in video_title if c.isalpha() or c.isdigit() or c in ' ._-']).rstrip()
        
        # --- Configure command based on download type (video or audio) ---
        if download_type == 'audio':
            output_filename = f"{safe_title}.mp3"
            output_path = os.path.join(DOWNLOAD_FOLDER, output_filename)
            command = [
                'yt-dlp', '--progress', '-f', 'bestaudio/best', '--extract-audio',
                '--audio-format', 'mp3', '--audio-quality', '0', # 0 is best
                '-o', output_path, video_url
            ]
        else: # Default to video
            output_filename = f"{safe_title}.mp4"
            output_path = os.path.join(DOWNLOAD_FOLDER, output_filename)
            command = [
                'yt-dlp', '--progress', '-f', 'bestvideo[height>=2160]+bestaudio/bestvideo+bestaudio/best',
                '--merge-output-format', 'mp4', '-o', output_path, video_url
            ]
        
        tasks[task_id]['filename'] = output_filename
        tasks[task_id]['status'] = 'downloading'
        tasks[task_id]['details'] = 'Starting download...'

        process = subprocess.Popen(
            command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, 
            universal_newlines=True, encoding='utf-8'
        )

        for line in process.stdout:
            match = re.search(r"\[download\]\s+([0-9.]+)%", line)
            if match:
                percent = float(match.group(1))
                tasks[task_id]['progress'] = percent
                tasks[task_id]['details'] = line.strip().replace('[download]', '').strip()

        process.wait()

        if process.returncode == 0:
            tasks[task_id]['status'] = 'complete'
            tasks[task_id]['progress'] = 100
            tasks[task_id]['details'] = 'Download complete! Your file is ready.'
        else:
            tasks[task_id]['status'] = 'error'
            tasks[task_id]['details'] = 'An error occurred during download.'

    except subprocess.CalledProcessError:
        tasks[task_id]['status'] = 'error'
        tasks[task_id]['details'] = 'Invalid URL or video is private/unavailable.'
    except Exception as e:
        tasks[task_id]['status'] = 'error'
        tasks[task_id]['details'] = f'An unexpected error occurred: {str(e)}'

# --- Flask Routes ---

@app.route('/')
def index():
    return render_template('download.html')

@app.route('/get-video-info', methods=['POST'])
def get_video_info():
    video_url = request.json.get('url')
    if not video_url:
        return jsonify({'error': 'URL is missing.'}), 400

    command = ['yt-dlp', '--dump-json', '--no-warnings', '--skip-download', video_url]
    try:
        proc = subprocess.run(command, capture_output=True, text=True, check=True, encoding='utf-8')
        video_data = json.loads(proc.stdout)
        info = {
            'title': video_data.get('title', 'N/A'),
            'uploader': video_data.get('uploader', 'N/A'),
            'thumbnail': video_data.get('thumbnail', ''),
            'duration_string': video_data.get('duration_string', 'N/A'),
            'view_count': format_number(video_data.get('view_count')),
            'like_count': format_number(video_data.get('like_count')),
            'upload_date': format_date(video_data.get('upload_date')),
            'resolution': video_data.get('resolution', 'Best Available')
        }
        return jsonify(info)
    except subprocess.CalledProcessError:
        return jsonify({'error': 'Invalid URL or video is private/unavailable.'}), 400
    except Exception as e:
        return jsonify({'error': f'An unexpected error occurred: {str(e)}'}), 500

@app.route('/start-download', methods=['POST'])
def start_download():
    video_url = request.json.get('url')
    download_type = request.json.get('type', 'video') # 'video' or 'audio'
    if not video_url:
        return jsonify({'error': 'URL is missing.'}), 400
    
    task_id = uuid.uuid4().hex
    thread = threading.Thread(target=download_thread, args=(task_id, video_url, download_type))
    thread.start()
    
    return jsonify({'task_id': task_id})

@app.route('/progress-stream/<task_id>')
def progress_stream(task_id):
    def generate():
        while True:
            task = tasks.get(task_id)
            if not task:
                error_task = {'status': 'error', 'details': 'Task ID not found.'}
                yield f"data: {json.dumps(error_task)}\n\n"
                break
            
            yield f"data: {json.dumps(task)}\n\n"
            if task['status'] in ['complete', 'error']:
                break
            time.sleep(0.5)

    return Response(generate(), mimetype='text/event-stream')

@app.route('/get-file/<filename>')
def get_file(filename):
    return send_from_directory(DOWNLOAD_FOLDER, filename, as_attachment=True)

if __name__ == '__main__':
    if not check_yt_dlp():
        print("❌ Fatal Error: 'yt-dlp' not found. Please run: pip install yt-dlp")
        sys.exit(1)
    
    print("✅ yt-dlp found.")
    print(f"🌍 Starting web server at http://127.0.0.1:5000")
    app.run(host='0.0.0.0', port=5000, debug=True)

