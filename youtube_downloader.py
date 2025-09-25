import yt_dlp
import json
import os
from flask import Response, stream_with_context
import queue
import threading
import re
import uuid
from werkzeug.utils import secure_filename
import random

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

def get_proxy_list():
    """Reads and shuffles a comma-separated list of proxies from the environment."""
    proxy_env = os.environ.get('PROXY_URL')
    if not proxy_env:
        return []
    proxies = [p.strip() for p in proxy_env.split(',')]
    random.shuffle(proxies)
    return proxies

# --- Core Unified Functions ---
def get_media_details(url):
    """Fetches details using a list of proxies, retrying on failure."""
    proxies = get_proxy_list()
    
    # Always try first without a proxy
    all_attempts = [None] + proxies 
    
    last_error = None

    for i, proxy in enumerate(all_attempts):
        ydl_opts = {
            'quiet': True, 'no_warnings': True, 'dump_single_json': True,
            'nocolor': True, 'socket_timeout': 15
        }
        if proxy:
            ydl_opts['proxy'] = proxy
            print(f"Attempt {i+1}/{len(all_attempts)}: Fetching details via proxy {proxy.split('@')[-1]}")
        else:
            print(f"Attempt 1/{len(all_attempts)}: Fetching details directly (no proxy).")

        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=False)
                # (The rest of the logic is the same if successful)
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
        except Exception as e:
            last_error = str(e).split('ERROR: ')[-1]
            print(f"Attempt {i+1} failed: {last_error}")
            continue # Try next proxy

    return {"error": f"Failed after {len(all_attempts)} attempts. Last error: {last_error}"}


def download_media(url, download_type='video'):
    """Downloads media with proxy rotation and retry logic."""
    q = queue.Queue()

    def download_thread_target(url, download_type, q):
        proxies = get_proxy_list()
        all_attempts = [None] + proxies
        last_error = None
        
        for i, proxy in enumerate(all_attempts):
            try:
                # --- This block runs once per proxy attempt ---
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
                    'progress_hooks': [progress_hook], 'outtmpl': {'default': temp_filepath},
                    'merge_output_format': 'mp4', 'nocolor': True, 'socket_timeout': 15
                }

                if proxy:
                    ydl_opts['proxy'] = proxy
                    print(f"Attempt {i+1}: Downloading via proxy {proxy.split('@')[-1]}")
                else:
                     print(f"Attempt 1: Downloading directly (no proxy).")
                
                if download_type == 'video':
                    ydl_opts['format'] = 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best'
                else:
                    ydl_opts.update({'format': 'bestaudio/best', 'postprocessors': [{'key': 'FFmpegExtractAudio', 'preferredcodec': 'mp3', 'preferredquality': '192'}]})

                with yt_dlp.YoutubeDL(ydl_opts) as ydl: ydl.download([url])
                
                downloaded_temp_file = next((f for f in os.listdir(DOWNLOADS_DIR) if f.startswith(f"__temp_{task_id}")), None)
                
                if downloaded_temp_file:
                    os.rename(os.path.join(DOWNLOADS_DIR, downloaded_temp_file), final_filepath)
                    q.put({'status': 'finished', 'filename': final_filename})
                    return # Exit thread on success
                else:
                    raise Exception('Could not find temporary file after download.')
            
            except Exception as e:
                last_error = str(e).split('ERROR: ')[-1]
                print(f"Download attempt {i+1} failed: {last_error}")
                continue # Try next proxy
        
        # This part is only reached if all attempts fail
        q.put({'status': 'error', 'message': f"All download attempts failed. Last error: {last_error}"})


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
                progress_data = {"status": "progress", "percent": percent, "speed": speed_str_clean, "eta": eta_str_clean}
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

