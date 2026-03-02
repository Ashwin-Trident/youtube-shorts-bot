import os
import random
import requests
from moviepy.editor import VideoFileClip, AudioFileClip
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from google.oauth2.credentials import Credentials
from TTS.api import TTS

TOPICS = ["AI", "Motivation", "Tech", "Finance", "Space"]
VIDEO_FILE = "video.mp4"
AUDIO_FILE = "voice.wav"
FINAL_FILE = "final.mp4"

PEXELS_API_KEY = os.environ.get("PEXELS_API_KEY")
YT_CLIENT_ID = os.environ.get("CLIENT_ID")
YT_CLIENT_SECRET = os.environ.get("CLIENT_SECRET")
YT_REFRESH_TOKEN = os.environ.get("REFRESH_TOKEN")

def generate_script():
    topic = random.choice(TOPICS)
    return f"""Did you know about {topic}?

Here are 3 amazing facts:

1. First fact...
2. Second fact...
3. Last mind-blowing fact!

Follow for more!
"""

def generate_voice(script):
    print("🎙️ Generating voice...")
    try:
        tts = TTS(model_name="tts_models/en/ljspeech/tacotron2-DDC")
        tts.tts_to_file(text=script, file_path=AUDIO_FILE)
        print("✅ Voice generated successfully.")
    except Exception as e:
        print("❌ Error generating voice:", e)
        raise

def download_video(query="technology"):
    print("📹 Downloading stock video...")
    try:
        headers = {"Authorization": PEXELS_API_KEY}
        r = requests.get(f"https://api.pexels.com/videos/search?query={query}&per_page=1", headers=headers).json()
        if not r.get("videos"):
            raise Exception("No videos found on Pexels.")
        # Pick highest resolution video
        url = sorted(r["videos"][0]["video_files"], key=lambda x: x["width"], reverse=True)[0]["link"]
        r2 = requests.get(url)
        with open(VIDEO_FILE, "wb") as f:
            f.write(r2.content)
        print("✅ Video downloaded successfully.")
    except Exception as e:
        print("❌ Error downloading video:", e)
        raise

def merge_video_audio():
    print("🔗 Merging video and audio...")
    try:
        video = VideoFileClip(VIDEO_FILE)
        audio = AudioFileClip(AUDIO_FILE)
        final = video.set_audio(audio)
        final.write_videofile(FINAL_FILE, codec="libx264", audio_codec="aac")
        print("✅ Video merged successfully.")
    except Exception as e:
        print("❌ Error merging video and audio:", e)
        raise

def upload_youtube():
    print("🚀 Uploading to YouTube Shorts...")
    try:
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
                    "title": "Amazing AI Fact",
                    "description": "Auto generated AI content",
                    "tags": ["ai", "facts", "shorts"],
                    "categoryId": "28"  # Science & Tech
                },
                "status": {"privacyStatus": "public"}
            },
            media_body=MediaFileUpload(FINAL_FILE)
        )
        response = request.execute()
        print("✅ Uploaded Video ID:", response["id"])
    except Exception as e:
        print("❌ Error uploading video:", e)
        raise

def main():
    try:
        print("🎬 Generating script...")
        script = generate_script()
        generate_voice(script)
        download_video()
        merge_video_audio()
        upload_youtube()
        print("✅ Video posted successfully!")
    except Exception as e:
        print("🚨 Bot failed:", e)

if __name__ == "__main__":
    main()
