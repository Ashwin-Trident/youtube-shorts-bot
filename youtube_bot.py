import os
import random
import base64
import json
from moviepy.editor import VideoFileClip, AudioFileClip, TextClip, ColorClip, CompositeVideoClip
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from google.oauth2.credentials import Credentials
from TTS.api import TTS

# -------------------------------
# Config
# -------------------------------
VIDEO_FILE = "animation.mp4"
AUDIO_FILE = "voice.wav"
FINAL_FILE = "final.mp4"
PEXELS_API_KEY = os.environ.get("PEXELS_API_KEY")
TOKEN_JSON_B64 = os.environ.get("TOKEN_JSON_B64")

# -------------------------------
# Thoughts / Quotes
# -------------------------------
THOUGHTS = [
    "Believe in yourself, even when no one else does.",
    "Small steps every day lead to big changes.",
    "Happiness is found within, not in things.",
    "Your mind is a garden. Plant positivity.",
    "Your thoughts create your reality.",
    "Challenges are opportunities in disguise.",
    "The only limit is your imagination.",
    "Consistency beats motivation every time.",
    "Kindness is free, sprinkle it everywhere.",
    "Dream big, start small, act now."
]

# -------------------------------
# Helper functions
# -------------------------------
def get_thought():
    return random.choice(THOUGHTS)

def generate_voice(text):
    print("🎙️ Generating voice...")
    tts = TTS(model_name="tts_models/en/ljspeech/tacotron2-DDC")
    tts.tts_to_file(text=text, file_path=AUDIO_FILE)
    print("✅ Voice generated successfully.")

def create_animation(text):
    print("🎨 Creating animated video...")
    bg = ColorClip(size=(720, 1280), color=(30, 30, 30)).set_duration(10)
    txt = TextClip(text, fontsize=60, color='white', size=(680, 1000), method='caption')
    txt = txt.set_position('center').set_duration(10).fadein(1).fadeout(1)
    video = CompositeVideoClip([bg, txt])
    video.write_videofile(VIDEO_FILE, fps=24)
    print("✅ Animation created successfully.")

def merge_audio_video():
    print("🔗 Merging audio and video...")
    video = VideoFileClip(VIDEO_FILE)
    audio = AudioFileClip(AUDIO_FILE)
    final = video.set_audio(audio)
    final.write_videofile(FINAL_FILE, codec="libx264", audio_codec="aac")
    print("✅ Video merged successfully.")

def upload_youtube():
    print("🚀 Uploading to YouTube Shorts...")
    if not TOKEN_JSON_B64:
        raise ValueError("ERROR: TOKEN_JSON_B64 secret is empty!")
    
    token_json = json.loads(base64.b64decode(TOKEN_JSON_B64).decode("utf-8"))
    creds = Credentials.from_authorized_user_info(token_json)
    
    youtube = build("youtube", "v3", credentials=creds)
    request = youtube.videos().insert(
        part="snippet,status",
        body={
            "snippet": {
                "title": "💡 Thoughtful Reel",
                "description": "Auto-generated thoughtful quote reel.",
                "tags": ["thoughts", "reels", "motivational", "shorts"],
                "categoryId": "22"
            },
            "status": {"privacyStatus": "public"}
        },
        media_body=MediaFileUpload(FINAL_FILE)
    )
    response = request.execute()
    print("✅ Uploaded Video ID:", response["id"])

# -------------------------------
# Main
# -------------------------------
def main():
    try:
        thought = get_thought()
        print(f"💭 Thought: {thought}")
        generate_voice(thought)
        create_animation(thought)
        merge_audio_video()
        upload_youtube()
        print("✅ Video posted successfully!")
    except Exception as e:
        print("🚨 Bot failed:", e)

if __name__ == "__main__":
    main()
