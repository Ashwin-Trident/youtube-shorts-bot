# youtube_bot.py

import os
import random
from moviepy.editor import VideoFileClip, AudioFileClip, TextClip, CompositeVideoClip, ColorClip
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from google.oauth2.credentials import Credentials
from TTS.api import TTS
import openai

# ----------------------------
# Environment Variables
# ----------------------------
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")
PEXELS_API_KEY = os.environ.get("PEXELS_API_KEY")
YT_CLIENT_ID = os.environ.get("CLIENT_ID")
YT_CLIENT_SECRET = os.environ.get("CLIENT_SECRET")
YT_REFRESH_TOKEN = os.environ.get("REFRESH_TOKEN")

# ----------------------------
# Filenames
# ----------------------------
VIDEO_FILE = "video.mp4"
AUDIO_FILE = "voice.wav"
FINAL_FILE = "final.mp4"

# ----------------------------
# Functions
# ----------------------------

def generate_ai_quote():
    """
    Generate a random thought/quote using OpenAI GPT.
    """
    print("💡 Generating AI quote...")
    openai.api_key = OPENAI_API_KEY
    prompt = "Give me one short thought-provoking quote suitable for a YouTube Shorts reel."
    response = openai.ChatCompletion.create(
        model="gpt-3.5-turbo",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.8,
        max_tokens=50
    )
    quote = response.choices[0].message.content.strip()
    print("✅ Quote generated:", quote)
    return quote

def generate_voice(text):
    """
    Generate voice using TTS from the quote.
    """
    print("🎙️ Generating voice...")
    tts = TTS(model_name="tts_models/en/ljspeech/tacotron2-DDC")
    tts.tts_to_file(text=text, file_path=AUDIO_FILE)
    print("✅ Voice generated successfully.")

def download_video(query="animation"):
    """
    Download a stock video from Pexels.
    """
    import requests
    print("📹 Downloading stock video...")
    headers = {"Authorization": PEXELS_API_KEY}
    r = requests.get(f"https://api.pexels.com/videos/search?query={query}&per_page=1", headers=headers).json()
    if not r.get("videos"):
        raise Exception("No videos found on Pexels.")
    url = sorted(r["videos"][0]["video_files"], key=lambda x: x["width"], reverse=True)[0]["link"]
    r2 = requests.get(url)
    with open(VIDEO_FILE, "wb") as f:
        f.write(r2.content)
    print("✅ Video downloaded successfully.")

def create_text_video(quote):
    """
    Create a video with text overlay using safe MoviePy TextClip.
    """
    print("🎨 Creating video with text...")
    video = VideoFileClip(VIDEO_FILE)
    txt_clip = TextClip(
        quote,
        fontsize=50,
        color="white",
        font="Arial-Bold",
        method="caption",
        size=(video.w * 0.8, None)
    ).set_position("center").set_duration(video.duration)

    final_clip = CompositeVideoClip([video, txt_clip])
    final_clip.write_videofile(FINAL_FILE, codec="libx264", audio_codec="aac")
    print("✅ Video created with quote.")

def upload_youtube():
    """
    Upload final video to YouTube Shorts.
    """
    print("🚀 Uploading to YouTube Shorts...")
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
                "title": "AI Thought for You",
                "description": "Auto-generated AI thought for YouTube Shorts",
                "tags": ["ai", "thoughts", "shorts", "motivation"],
                "categoryId": "28"
            },
            "status": {"privacyStatus": "public"}
        },
        media_body=MediaFileUpload(FINAL_FILE)
    )
    response = request.execute()
    print("✅ Uploaded Video ID:", response["id"])

# ----------------------------
# Main Bot
# ----------------------------
def main():
    try:
        quote = generate_ai_quote()
        generate_voice(quote)
        download_video()
        create_text_video(quote)
        upload_youtube()
        print("✅ Video posted successfully!")
    except Exception as e:
        print("🚨 Bot failed:", e)

if __name__ == "__main__":
    main()
