# youtube_bot.py (100% FREE VERSION - NO OPENAI)

import os
import random
import requests
from moviepy.editor import VideoFileClip, AudioFileClip, TextClip, CompositeVideoClip
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from google.oauth2.credentials import Credentials
from TTS.api import TTS

# =============================
# ENV VARIABLES
# =============================

PEXELS_API_KEY = os.environ.get("PEXELS_API_KEY")
CLIENT_ID = os.environ.get("CLIENT_ID")
CLIENT_SECRET = os.environ.get("CLIENT_SECRET")
REFRESH_TOKEN = os.environ.get("REFRESH_TOKEN")

VIDEO_FILE = "video.mp4"
AUDIO_FILE = "voice.wav"
FINAL_FILE = "final.mp4"

# =============================
# 1️⃣ FREE AI-STYLE QUOTE GENERATOR
# =============================

topics = [
    "success", "dreams", "discipline", "mindset",
    "happiness", "future", "technology", "life"
]

quote_templates = [
    "Your {topic} depends on what you do today.",
    "Small steps create big {topic}.",
    "The secret to {topic} is consistency.",
    "If you believe in your {topic}, nothing can stop you.",
    "{topic.capitalize()} begins the moment you decide."
]

def generate_quote():
    topic = random.choice(topics)
    template = random.choice(quote_templates)
    quote = template.format(topic=topic)
    print("💡 Generated Quote:", quote)
    return quote, topic


# =============================
# 2️⃣ Generate Voice (FREE)
# =============================

def generate_voice(text):
    print("🎙 Generating voice...")
    tts = TTS(model_name="tts_models/en/ljspeech/tacotron2-DDC")
    tts.tts_to_file(text=text, file_path=AUDIO_FILE)
    print("✅ Voice created")


# =============================
# 3️⃣ Download Vertical Video
# =============================

def download_video(query):
    print("📥 Downloading stock video...")
    headers = {"Authorization": PEXELS_API_KEY}
    url = f"https://api.pexels.com/videos/search?query={query}&orientation=portrait&per_page=1"

    response = requests.get(url, headers=headers).json()

    if not response.get("videos"):
        raise Exception("No video found!")

    video_url = response["videos"][0]["video_files"][0]["link"]

    r = requests.get(video_url)
    with open(VIDEO_FILE, "wb") as f:
        f.write(r.content)

    print("✅ Video downloaded")


# =============================
# 4️⃣ Create Final Shorts Video
# =============================

def create_video(quote):
    print("🎬 Creating final video...")

    video = VideoFileClip(VIDEO_FILE).subclip(0, 15)

    text_clip = TextClip(
        quote,
        fontsize=60,
        color="white",
        method="caption",
        size=(video.w * 0.8, None)
    ).set_position("center").set_duration(video.duration)

    final = CompositeVideoClip([video, text_clip])

    audio = AudioFileClip(AUDIO_FILE)
    final = final.set_audio(audio)

    final.write_videofile(FINAL_FILE, codec="libx264", audio_codec="aac")

    print("✅ Final video created")


# =============================
# 5️⃣ Upload to YouTube
# =============================

def upload_youtube():
    print("🚀 Uploading to YouTube Shorts...")

    creds = Credentials(
        None,
        refresh_token=REFRESH_TOKEN,
        token_uri="https://oauth2.googleapis.com/token",
        client_id=CLIENT_ID,
        client_secret=CLIENT_SECRET
    )

    youtube = build("youtube", "v3", credentials=creds)

    request = youtube.videos().insert(
        part="snippet,status",
        body={
            "snippet": {
                "title": "Daily Motivation 🔥 #shorts",
                "description": "Auto generated motivational short",
                "tags": ["shorts", "motivation"],
                "categoryId": "28"
            },
            "status": {"privacyStatus": "public"}
        },
        media_body=MediaFileUpload(FINAL_FILE)
    )

    response = request.execute()
    print("✅ Uploaded Video ID:", response["id"])


# =============================
# MAIN
# =============================

def main():
    try:
        quote, topic = generate_quote()
        generate_voice(quote)
        download_video(topic)
        create_video(quote)
        upload_youtube()
        print("🎉 SUCCESS: Shorts uploaded!")
    except Exception as e:
        print("🚨 Bot failed:", e)


if __name__ == "__main__":
    main()
