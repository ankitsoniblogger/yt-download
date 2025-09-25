import yt_dlp
import json
import os
from flask import Response, stream_with_context

# --- Global Settings ---
DOWNLOADS_DIR = '/app/downloads' if os.path.exists('/app') else 'downloads'
if not os.path.exists(DOWNLOADS_DIR):
    os.makedirs(DOWNLOADS_DIR)

# --- Helper Functions ---
def format_views(view_count):
    if view_count is None:
        return "N/A"
    return f"{view_count:,}"

def format_duration(seconds):
    if seconds is None:
        return "N/A"
    minutes, seconds = divmod(int(seconds), 60)
    hours, minutes = divmod(minutes, 60)
    if hours > 0:
        return f"{hours:02}:{minutes:02}:{seconds:02}"
    return f"{minutes:02}:{seconds:02}"

# --- Core Unified Functions ---
def get_media_details(url):
    """
    Fetches details for a YouTube, Instagram, or Pinterest URL using yt-dlp.
    """
    ydl_opts = {
        'quiet': True,
        'no_warnings': True,
        'dump_single_json': True,
    }
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            
            extractor = info.get('extractor_key', '').lower()
            
            # Determine platform
            platform = "youtube"
            if 'instagram' in extractor:
                platform = 'instagram'
            elif 'pinterest' in extractor:
                platform = 'pinterest'

            thumbnail_url = info.get('thumbnail', '')
            if (platform in ['instagram', 'pinterest']) and info.get('thumbnails'):
                thumbnail_url = info['thumbnails'][-1].get('url', thumbnail_url)

            views_or_likes = info.get('view_count')
            author = info.get('uploader', 'N/A')
            
            if platform == 'instagram':
                views_or_likes = info.get('like_count')
            elif platform == 'pinterest':
                views_or_likes = info.get('repin_count', info.get('comment_count'))
                author = info.get('uploader_id', author)

            details = {
                "type": platform,
                "title": info.get('title', 'N/A'),
                "author": author,
                "thumbnail_url": thumbnail_url,
                "duration": info.get('duration'),
                "views": views_or_likes,
                "url": url,
            }
            return details
    except yt_dlp.utils.DownloadError as e:
        error_str = str(e).lower()
        print(f"yt-dlp download error: {e}")
        if "private" in error_str:
            return {"error": "This content is private and cannot be accessed."}
        if "unavailable" in error_str:
            return {"error": "This content is unavailable or has been deleted."}
        return {"error": "Failed to fetch details. The URL may be incorrect or the content is geo-restricted."}
    except Exception as e:
        print(f"Unexpected error in get_media_details: {e}")
        return {"error": "An unexpected server error occurred. Please try again later."}

def download_media(url, download_type='video'):
    """
    Downloads media from YouTube, Instagram, or Pinterest and streams progress.
    """
    def generate_progress():
        try:
            # --- FIX: ADDED INITIAL YIELD FOR IMMEDIATE FEEDBACK ---
            # Immediately send a starting event to show the UI is responsive
            yield f"data: {json.dumps({'status': 'progress', 'percent': 1, 'speed': 'Starting...', 'eta': 'Calculating...'})}\n\n"

            ydl_temp = yt_dlp.YoutubeDL({'quiet': True, 'no_warnings': True})
            info = ydl_temp.extract_info(url, download=False)
            title = info.get('title', 'media_file')
            extractor = info.get('extractor_key', '').lower()
            platform = 'pinterest' if 'pinterest' in extractor else 'default'
            
            safe_title = "".join(c for c in title if c.isalnum() or c in (' ', '_', '-')).strip()
            if not safe_title:
                 safe_title = 'media_file'
            
            file_extension = "mp4" if download_type == 'video' else "mp3"
            filename = f"{safe_title}.{file_extension}"
            filepath = os.path.join(DOWNLOADS_DIR, filename)

            def progress_hook(d):
                if d['status'] == 'downloading':
                    percent_str = d.get('_percent_str', '0%').replace('%','').strip()
                    percent = float(percent_str)
                    speed = d.get('_speed_str', 'N/A')
                    eta = d.get('_eta_str', 'N/A')
                    
                    progress_data = { "status": "progress", "percent": percent, "speed": speed, "eta": eta }
                    yield f"data: {json.dumps(progress_data)}\n\n"

            ydl_opts = {
                'progress_hooks': [progress_hook],
                'outtmpl': {'default': filepath}, 
                'merge_output_format': 'mp4',
            }
            
            if download_type == 'video':
                if platform == 'pinterest':
                    ydl_opts['format'] = 'bestvideo[ext=mp4]/best[ext=mp4]/best'
                else:
                    ydl_opts['format'] = 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best'
            else:
                ydl_opts['format'] = 'bestaudio/best'
                ydl_opts['postprocessors'] = [{
                    'key': 'FFmpegExtractAudio',
                    'preferredcodec': 'mp3',
                    'preferredquality': '192',
                }]

            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([url])
            
            download_url = f"/get-file/{filename}"
            completion_data = { "status": "finished", "download_url": download_url }
            yield f"data: {json.dumps(completion_data)}\n\n"
            
        except Exception as e:
            print(f"Error during download process: {e}")
            error_data = {"status": "error", "message": str(e).split('ERROR: ')[-1]}
            yield f"data: {json.dumps(error_data)}\n\n"

    return Response(stream_with_context(generate_progress()), mimetype='text/event-stream')

