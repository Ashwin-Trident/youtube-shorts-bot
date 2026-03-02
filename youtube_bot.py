# youtube_shorts_bot.py
import os
import random
import requests
from moviepy.editor import (
    VideoFileClip,
    AudioFileClip,
    TextClip,
    CompositeVideoClip,
    ColorClip,
    CompositeAudioClip
)
from gtts import gTTS
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from google.oauth2.credentials import Credentials

# -----------------------------
# CONFIGURATION
# -----------------------------
VIDEO_FILE = "stock_video.mp4"
AUDIO_FILE = "voice.mp3"
FINAL_FILE = "final.mp4"
BG_MUSIC = "bg_music.mp3"  # optional, put a free loop here

# YouTube API credentials from GitHub Secrets or local environment
YT_CLIENT_ID = os.environ.get("CLIENT_ID")
YT_CLIENT_SECRET = os.environ.get("CLIENT_SECRET")
YT_REFRESH_TOKEN = os.environ.get("REFRESH_TOKEN")
PEXELS_API_KEY = os.environ.get("PEXELS_API_KEY")

# Video settings
WIDTH, HEIGHT = 1080, 1920  # vertical
DURATION = 10  # seconds

# -----------------------------
# UTILITY FUNCTIONS
# -----------------------------

def get_random_quote():
    """Returns a free viral-style quote from a predefined list"""
    quotes = [
        "Your limitation—it's only your imagination.",
        "Push yourself, because no one else is going to do it for you.",
        "Great things never come from comfort zones.",
        "Dream it. Wish it. Do it.",
        "Success doesn’t just find you. You have to go out and get it.",
        "Little things make big days.",
        "Don’t stop when you’re tired. Stop when you’re done.",
        "It’s going to be hard, but hard does not mean impossible.",
        "Wake up with determination. Go to bed with satisfaction.",
        "Do something today that your future self will thank you for."
    ]
    return random.choice(quotes)

def generate_voice(text, output_file=AUDIO_FILE):
    print("🎙️ Generating voice...")
    tts = gTTS(text=text, lang='en')
    tts.save(output_file)
    print("✅ Voice generated.")

def download_stock_video(query="nature"):
    print("📹 Downloading stock video...")
    headers = {"Authorization": PEXELS_API_KEY}
    r = requests.get(f"https://api.pexels.com/videos/search?query={query}&per_page=1", headers=headers).json()
    if not r.get("videos"):
        raise Exception("No videos found on Pexels.")
    url = sorted(r["videos"][0]["video_files"], key=lambda x: x["width"], reverse=True)[0]["link"]
    r2 = requests.get(url)
    with open(VIDEO_FILE, "wb") as f:
        f.write(r2.content)
    print("✅ Video downloaded.")

def create_shorts_video(quote_text):
    print("🎨 Creating animated video...")
    # Background color clip
    bg_clip = ColorClip(size=(WIDTH, HEIGHT), color=(30, 30, 30), duration=DURATION)

    # Text animation
    txt_clip = TextClip(
        txt=quote_text,
        fontsize=80,
        color='white',
        method='caption',
        size=(WIDTH - 100, None)
    ).set_position('center').set_duration(DURATION).fadein(0.5).fadeout(0.5)

    # Load stock video and resize vertically
    if os.path.exists(VIDEO_FILE):
        video_clip = VideoFileClip(VIDEO_FILE).resize(height=HEIGHT)
        video_clip = video_clip.crop(x_center=video_clip.w/2, width=WIDTH, y_center=video_clip.h/2, height=HEIGHT)
        video_clip = video_clip.set_duration(DURATION)
        final_clip = CompositeVideoClip([video_clip, txt_clip])
    else:
        final_clip = CompositeVideoClip([bg_clip, txt_clip])

    # Audio
    voice_clip = AudioFileClip(AUDIO_FILE)
    audio_clips = [voice_clip]
    if os.path.exists(BG_MUSIC):
        music_clip = AudioFileClip(BG_MUSIC).volumex(0.2).set_duration(DURATION)
        audio_clips.append(music_clip)
    final_audio = CompositeAudioClip(audio_clips)

    final_clip = final_clip.set_audio(final_audio)
    final_clip.write_videofile(FINAL_FILE, fps=24, codec="libx264", audio_codec="aac")
    print("✅ Video created successfully.")

def upload_to_youtube(title="Viral Quote #Shorts", description="Auto-generated YouTube Shorts", tags=None):
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
                "title": title,
                "description": description,
                "tags": tags or ["quotes", "shorts", "viral"],
                "categoryId": "22"  # People & Blogs
            },
            "status": {"privacyStatus": "public"}
        },
        media_body=MediaFileUpload(FINAL_FILE)
    )
    response = request.execute()
    print("✅ Uploaded Video ID:", response["id"])

# -----------------------------
# MAIN BOT
# -----------------------------

def main():
    try:
        quote = get_random_quote()
        generate_voice(quote)
        download_stock_video(query="inspiration")  # choose video theme
        create_shorts_video(quote)
        upload_to_youtube(title=f"{quote} #Shorts")
        print("✅ YouTube Shorts posted successfully!")
    except Exception as e:
        print("🚨 Bot failed:", e)

if __name__ == "__main__":
    main()
