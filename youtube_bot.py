import os
import random
import requests
from moviepy.editor import VideoFileClip, AudioFileClip, TextClip, CompositeVideoClip
from gtts import gTTS
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from google.oauth2.credentials import Credentials

# Files
VIDEO_FILE = "video.mp4"
AUDIO_FILE = "voice.mp3"
FINAL_FILE = "final.mp4"

# Pexels API
PEXELS_API_KEY = os.environ.get("PEXELS_API_KEY")

# YouTube API
YT_CLIENT_ID = os.environ.get("CLIENT_ID")
YT_CLIENT_SECRET = os.environ.get("CLIENT_SECRET")
YT_REFRESH_TOKEN = os.environ.get("REFRESH_TOKEN")


def get_quote():
    """Fetch a random quote from Quotable (free API)"""
    r = requests.get("https://api.quotable.io/random")
    data = r.json()
    return f"{data['content']} — {data['author']}"


def download_video():
    """Download a free stock video from Pexels"""
    headers = {"Authorization": PEXELS_API_KEY}
    r = requests.get("https://api.pexels.com/videos/search?query=nature&per_page=1", headers=headers).json()
    if not r.get("videos"):
        raise Exception("No videos found on Pexels.")
    url = sorted(r["videos"][0]["video_files"], key=lambda x: x["width"], reverse=True)[0]["link"]
    r2 = requests.get(url)
    with open(VIDEO_FILE, "wb") as f:
        f.write(r2.content)
    print("✅ Video downloaded successfully.")


def generate_voice(quote):
    """Convert quote to speech"""
    tts = gTTS(quote)
    tts.save(AUDIO_FILE)
    print("✅ Voice generated successfully.")


def merge_video_audio(quote):
    """Overlay quote text on video and merge with voice"""
    video = VideoFileClip(VIDEO_FILE)
    audio = AudioFileClip(AUDIO_FILE)

    txt_clip = TextClip(quote, fontsize=50, color='white', font='Arial-Bold',
                        size=(video.w, None), method='caption', align='center')
    txt_clip = txt_clip.set_duration(video.duration).set_position('center')

    final = CompositeVideoClip([video, txt_clip])
    final = final.set_audio(audio)
    final.write_videofile(FINAL_FILE, codec="libx264", audio_codec="aac")
    print("✅ Video merged successfully.")


def upload_youtube():
    """Upload the final video to YouTube Shorts"""
    creds = Credentials(
        None,
        refresh_token=YT_REFRESH_TOKEN,
        client_id=YT_CLIENT_ID,
        client_secret=YT_CLIENT_SECRET,
        token_uri="https://oauth2.googleapis.com/token"
    )
    youtube = build("youtube", "v3", credentials=creds)
    request = youtube.videos().insert(
        part="snippet,status",
        body={
            "snippet": {
                "title": "Viral Quote Shorts",
                "description": "Automatically generated quote video",
                "tags": ["quotes", "viral", "shorts"],
                "categoryId": "22"  # People & Blogs
            },
            "status": {"privacyStatus": "public"}
        },
        media_body=MediaFileUpload(FINAL_FILE)
    )
    response = request.execute()
    print("✅ Uploaded Video ID:", response["id"])


def main():
    quote = get_quote()
    print("💡 Quote:", quote)
    download_video()
    generate_voice(quote)
    merge_video_audio(quote)
    upload_youtube()
    print("🎉 Done!")


if __name__ == "__main__":
    main()
