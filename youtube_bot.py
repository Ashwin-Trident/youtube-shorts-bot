import os
import requests
import random
from moviepy.editor import VideoFileClip, TextClip, CompositeVideoClip, concatenate_videoclips, AudioFileClip
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
import base64
import tempfile

# -------------------------------
# Environment variables from GitHub Actions
# -------------------------------
TOKEN_JSON_B64 = os.getenv("TOKEN_JSON_B64")
PEXELS_API_KEY = os.getenv("PEXELS_API_KEY")

if not TOKEN_JSON_B64 or not PEXELS_API_KEY:
    raise Exception("Set TOKEN_JSON_B64 and PEXELS_API_KEY as GitHub Secrets.")

# Decode token.json
token_bytes = base64.b64decode(TOKEN_JSON_B64)
token_file = tempfile.NamedTemporaryFile(delete=False, suffix=".json")
token_file.write(token_bytes)
token_file.close()

# -------------------------------
# 1. Generate a random quote (free)
# -------------------------------
def get_quote():
    try:
        r = requests.get("https://api.quotable.io/random", timeout=10)
        data = r.json()
        return f"{data['content']} — {data['author']}"
    except:
        # fallback quotes if API fails
        quotes = [
            "Success comes from persistence. — Unknown",
            "Believe you can and you're halfway there. — Theodore Roosevelt",
            "Do one thing every day that scares you. — Eleanor Roosevelt"
        ]
        return random.choice(quotes)

# -------------------------------
# 2. Get free video from Pexels
# -------------------------------
def get_video_for_keyword(keyword):
    headers = {"Authorization": PEXELS_API_KEY}
    params = {"query": keyword, "orientation": "portrait", "size": "medium", "per_page": 1}
    r = requests.get("https://api.pexels.com/videos/search", headers=headers, params=params, timeout=10)
    results = r.json()
    if results["videos"]:
        video_url = results["videos"][0]["video_files"][0]["link"]
        local_file = tempfile.NamedTemporaryFile(delete=False, suffix=".mp4")
        video_data = requests.get(video_url).content
        local_file.write(video_data)
        local_file.close()
        return local_file.name
    else:
        raise Exception("No video found for keyword:", keyword)

# -------------------------------
# 3. Create YouTube Shorts video
# -------------------------------
def create_youtube_short(quote):
    # Pick first word as keyword for video search
    keyword = quote.split()[0]
    video_path = get_video_for_keyword(keyword)
    
    # Load video and trim to 15 seconds
    clip = VideoFileClip(video_path).subclip(0, min(15, VideoFileClip(video_path).duration))
    
    # Add text overlay
    txt_clip = TextClip(
        quote, fontsize=50, color="white", size=(clip.w-50, None),
        method='caption', align='center'
    ).set_position('center').set_duration(clip.duration)
    
    final_clip = CompositeVideoClip([clip, txt_clip])
    
    output_file = os.path.join(tempfile.gettempdir(), "youtube_short.mp4")
    final_clip.write_videofile(output_file, fps=24, codec="libx264", audio_codec="aac")
    return output_file

# -------------------------------
# 4. Upload video to YouTube
# -------------------------------
def upload_to_youtube(video_file, title):
    creds = Credentials.from_authorized_user_file(token_file.name)
    youtube = build("youtube", "v3", credentials=creds)

    request = youtube.videos().insert(
        part="snippet,status",
        body={
            "snippet": {
                "title": title,
                "description": "Auto-generated YouTube Shorts video",
                "tags": ["shorts", "AI", "quotes"],
                "categoryId": "22"
            },
            "status": {
                "privacyStatus": "public"
            }
        },
        media_body=video_file
    )
    response = request.execute()
    print("✅ Video uploaded. Video ID:", response.get("id"))

# -------------------------------
# Main
# -------------------------------
def main():
    quote = get_quote()
    print("💡 Selected quote:", quote)
    video_file = create_youtube_short(quote)
    upload_to_youtube(video_file, title=quote[:70]+"...")  # Title max 100 chars

if __name__ == "__main__":
    main()
