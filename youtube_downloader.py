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

            # --- Thumbnail Logic Improvement ---
            thumbnail_url = info.get('thumbnail', '')
            if (platform in ['instagram', 'pinterest']) and info.get('thumbnails'):
                thumbnail_url = info['thumbnails'][-1].get('url', thumbnail_url)

            # --- Platform-Specific Metadata Handling ---
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
        print(f"yt-dlp download error: {e}")
        return {"error": "Failed to fetch details. The content may be private, deleted, or the URL is incorrect."}
    except Exception as e:
        print(f"Unexpected error in get_media_details: {e}")
        return {"error": "An unexpected error occurred while fetching details."}

def download_media(url, download_type='video'):
    """
    Downloads media from YouTube, Instagram, or Pinterest and streams progress.
    """
    def generate_progress():
        
        # Prepare filename and determine platform
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

        # Progress Hook for yt-dlp
        def progress_hook(d):
            if d['status'] == 'downloading':
                percent_str = d.get('_percent_str', '0%').replace('%','').strip()
                percent = float(percent_str)
                speed = d.get('_speed_str', 'N/A')
                eta = d.get('_eta_str', 'N/A')
                
                progress_data = { "status": "progress", "percent": percent, "speed": speed, "eta": eta }
                yield f"data: {json.dumps(progress_data)}\n\n"

        # yt-dlp Options
        ydl_opts = {
            'progress_hooks': [progress_hook],
            'outtmpl': {'default': filepath}, 
            'merge_output_format': 'mp4',
        }
        
        if download_type == 'video':
            # --- FIX FOR PINTEREST ---
            # Use a more flexible format for Pinterest, which often uses HLS streams (m3u8)
            if platform == 'pinterest':
                ydl_opts['format'] = 'bestvideo[ext=mp4]/best[ext=mp4]/best'
            else:
                # The robust format for YouTube and Instagram
                ydl_opts['format'] = 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best'
        else: # audio
            ydl_opts['format'] = 'bestaudio/best'
            ydl_opts['postprocessors'] = [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': '192',
            }]

        # Start Download
        try:
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

