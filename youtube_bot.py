import os
import random
import requests
import base64
from moviepy.editor import VideoFileClip, AudioFileClip
from TTS.api import TTS
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
import json

# -------------------------
# CONFIG
# -------------------------
TOPICS = ["AI", "Motivation", "Tech", "Finance", "Space"]
VIDEO_FILE = "video.mp4"
AUDIO_FILE = "voice.wav"
FINAL_FILE = "final.mp4"
SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]

PEXELS_API_KEY = os.environ.get("PEXELS_API_KEY")
TOKEN_JSON_B64 = os.environ.get("TOKEN_JSON_B64")  # base64 token.json from GitHub secrets

# -------------------------
# FUNCTIONS
# -------------------------
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
    tts = TTS(model_name="tts_models/en/ljspeech/tacotron2-DDC")
    tts.tts_to_file(text=script, file_path=AUDIO_FILE)
    print("✅ Voice generated successfully.")

def download_video(query="technology"):
    print("📹 Downloading stock video...")
    headers = {"Authorization": PEXELS_API_KEY}
    r = requests.get(f"https://api.pexels.com/videos/search?query={query}&per_page=1", headers=headers)
    if r.status_code != 200:
        raise Exception(f"Pexels API error: {r.status_code} - {r.text}")
    data = r.json()
    if not data.get("videos"):
        raise Exception("No videos found on Pexels.")
    url = sorted(data["videos"][0]["video_files"], key=lambda x: x["width"], reverse=True)[0]["link"]
    r2 = requests.get(url)
    with open(VIDEO_FILE, "wb") as f:
        f.write(r2.content)
    print("✅ Video downloaded successfully.")

def merge_video_audio():
    print("🔗 Merging video and audio...")
    video = VideoFileClip(VIDEO_FILE)
    audio = AudioFileClip(AUDIO_FILE)
    final = video.set_audio(audio)
    final.write_videofile(FINAL_FILE, codec="libx264", audio_codec="aac")
    print("✅ Video merged successfully.")

def upload_youtube():
    print("🚀 Uploading to YouTube Shorts...")

    if not TOKEN_JSON_B64:
        raise ValueError("ERROR: TOKEN_JSON_B64 secret is empty!")

    try:
        decoded = base64.b64decode(TOKEN_JSON_B64).decode("utf-8")
    except Exception as e:
        raise ValueError(f"ERROR: Failed to decode TOKEN_JSON_B64: {e}")

    if not decoded.strip().startswith("{"):
        raise ValueError("ERROR: Decoded TOKEN_JSON_B64 is not valid JSON.")

    with open("token.json", "w") as f:
        f.write(decoded)
    print("✅ token.json written successfully.")

    creds = Credentials.from_authorized_user_file("token.json", SCOPES)
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

# -------------------------
# MAIN
# -------------------------
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
