import yt_dlp
import json
import os
from flask import Response, stream_with_context
import queue
import threading
import re
import uuid
from werkzeug.utils import secure_filename

# --- Global Settings ---
DOWNLOADS_DIR = '/app/downloads' if os.path.exists('/app') else 'downloads'
if not os.path.exists(DOWNLOADS_DIR):
    os.makedirs(DOWNLOADS_DIR)

# --- Helper Functions ---
def format_views(view_count):
    if view_count is None: return "N/A"
    return f"{view_count:,}"

def format_duration(seconds):
    if seconds is None: return "N/A"
    minutes, seconds = divmod(int(seconds), 60)
    hours, minutes = divmod(minutes, 60)
    return f"{hours:02}:{minutes:02}:{seconds:02}" if hours > 0 else f"{minutes:02}:{seconds:02}"

# --- Core Unified Functions ---
def get_media_details(url):
    """Fetches details for a URL using yt-dlp, with proxy support."""
    ydl_opts = {
        'quiet': True,
        'no_warnings': True,
        'dump_single_json': True,
        'nocolor': True,
    }
    # --- PROXY INTEGRATION: Read from environment variables ---
    proxy = os.environ.get('PROXY_URL')
    if proxy:
        ydl_opts['proxy'] = proxy
        print("Using proxy for fetching details.")

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            extractor = info.get('extractor_key', '').lower()
            
            platform_map = {'instagram': 'instagram', 'pinterest': 'pinterest'}
            platform = next((p for key, p in platform_map.items() if key in extractor), 'youtube')

            thumbnail_url = info.get('thumbnail', '')
            if (platform in ['instagram', 'pinterest']) and info.get('thumbnails'):
                thumbnail_url = info['thumbnails'][-1].get('url', thumbnail_url)

            views_map = {'instagram': 'like_count', 'pinterest': 'repin_count'}
            views_or_likes = info.get(views_map.get(platform, 'view_count'))

            author = info.get('uploader_id') if platform == 'pinterest' else info.get('uploader', 'N/A')

            return {
                "type": platform, "title": info.get('title', 'N/A'),
                "author": author, "thumbnail_url": thumbnail_url,
                "duration": info.get('duration'), "views": views_or_likes, "url": url
            }
    except yt_dlp.utils.DownloadError as e:
        error_str = str(e).lower()
        if "private" in error_str: return {"error": "This content is private."}
        if "unavailable" in error_str: return {"error": "This content is unavailable or deleted."}
        return {"error": "Failed to fetch details. URL may be incorrect or geo-restricted."}
    except Exception as e:
        print(f"Unexpected error in get_media_details: {e}")
        return {"error": "An unexpected server error occurred."}

def download_media(url, download_type='video'):
    """
    Downloads media using a standardized, secure filename and proxy support.
    """
    q = queue.Queue()

    def download_thread_target(url, download_type, q):
        try:
            ydl_temp = yt_dlp.YoutubeDL({'quiet': True, 'no_warnings': True})
            info = ydl_temp.extract_info(url, download=False)
            title = info.get('title', 'media_file')
            
            base_filename = os.path.splitext(secure_filename(title))[0] or 'media_file'
            final_extension = 'mp4' if download_type == 'video' else 'mp3'
            final_filename = f"{base_filename}.{final_extension}"
            final_filepath = os.path.join(DOWNLOADS_DIR, final_filename)
            
            task_id = str(uuid.uuid4())
            temp_filename_template = f"__temp_{task_id}.%(ext)s"
            temp_filepath = os.path.join(DOWNLOADS_DIR, temp_filename_template)

            def progress_hook(d):
                if d['status'] == 'downloading': q.put(d)

            ydl_opts = {
                'progress_hooks': [progress_hook],
                'outtmpl': {'default': temp_filepath},
                'merge_output_format': 'mp4',
                'nocolor': True,
            }

            # --- PROXY INTEGRATION: Read from environment variables ---
            proxy = os.environ.get('PROXY_URL')
            if proxy:
                ydl_opts['proxy'] = proxy
                print("Using proxy for download.")
            
            if download_type == 'video':
                ydl_opts['format'] = 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best'
            else: # audio
                ydl_opts.update({
                    'format': 'bestaudio/best',
                    'postprocessors': [{'key': 'FFmpegExtractAudio', 'preferredcodec': 'mp3', 'preferredquality': '192'}]
                })

            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([url])

            downloaded_temp_file = None
            for f in os.listdir(DOWNLOADS_DIR):
                if f.startswith(f"__temp_{task_id}"):
                    downloaded_temp_file = f
                    break
            
            if downloaded_temp_file:
                os.rename(os.path.join(DOWNLOADS_DIR, downloaded_temp_file), final_filepath)
                q.put({'status': 'finished', 'filename': final_filename})
            else:
                 q.put({'status': 'error', 'message': 'Could not find temporary file after download.'})

        except Exception as e:
            q.put({'status': 'error', 'message': str(e).split('ERROR: ')[-1]})

    thread = threading.Thread(target=download_thread_target, args=(url, download_type, q), daemon=True)
    thread.start()

    def generate_progress():
        yield f"data: {json.dumps({'status': 'progress', 'percent': 1, 'speed': 'Initializing...', 'eta': '...'})}\n\n"
        ansi_escape = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')
        while True:
            data = q.get()
            if data['status'] == 'downloading':
                percent_str_raw = data.get('_percent_str', '0%')
                speed_str_raw = data.get('_speed_str', 'N/A')
                eta_str_raw = data.get('_eta_str', 'N/A')

                percent_str_clean = ansi_escape.sub('', percent_str_raw).strip()
                speed_str_clean = ansi_escape.sub('', speed_str_raw).strip()
                eta_str_clean = ansi_escape.sub('', eta_str_raw).strip()
                
                try: percent = float(percent_str_clean.replace('%','').strip())
                except: percent = 0.0

                progress_data = {
                    "status": "progress", "percent": percent,
                    "speed": speed_str_clean, "eta": eta_str_clean
                }
                yield f"data: {json.dumps(progress_data)}\n\n"
            elif data['status'] == 'finished':
                completion_data = {"status": "finished", "download_url": f"/get-file/{data['filename']}"}
                yield f"data: {json.dumps(completion_data)}\n\n"
                break
            elif data['status'] == 'error':
                error_data = {"status": "error", "message": data['message']}
                yield f"data: {json.dumps(error_data)}\n\n"
                break
    
    return Response(stream_with_context(generate_progress()), mimetype='text/event-stream')

