import os
import json
import random
import requests
from moviepy.editor import VideoFileClip, TextClip, CompositeVideoClip, AudioFileClip
from TTS.api import TTS
from googleapiclient.discovery import build
from google.oauth2.credentials import Credentials
from base64 import b64decode

# ----------------- Config -----------------
PEXELS_API_KEY = os.environ.get("PEXELS_API_KEY")
YOUTUBE_TOKEN_JSON_B64 = os.environ.get("TOKEN_JSON_B64")  # base64 of token.json
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")            # optional
FINAL_FILE = "final.mp4"
VIDEO_FILE = "background.mp4"
AUDIO_FILE = "voice.wav"

# ----------------- AI-Generated Quote -----------------
def generate_ai_quote():
    """
    Generates a topic and quote.
    Uses OpenAI API if available, otherwise falls back to random quotes.
    """
    if OPENAI_API_KEY:
        try:
            import openai
            openai.api_key = OPENAI_API_KEY
            prompt = (
                "Generate a short, catchy YouTube Shorts topic and quote. "
                "Return JSON like: {\"topic\": \"Motivation\", \"quote\": \"Believe in yourself!\"}"
            )
            response = openai.ChatCompletion.create(
                model="gpt-3.5-turbo",
                messages=[{"role":"user","content":prompt}],
                temperature=0.8
            )
            data = json.loads(response.choices[0].message['content'])
            return data['topic'], data['quote']
        except Exception as e:
            print("⚠️ OpenAI API failed, using fallback:", e)

    # fallback free random quotes
    topics = ["Motivation","Tech","Space","Life","Inspiration"]
    quotes = [
        "Believe in yourself!",
        "Every day is a new opportunity.",
        "Technology shapes our future.",
        "Happiness is in small moments.",
        "The universe is vast and amazing."
    ]
    return random.choice(topics), random.choice(quotes)

# ----------------- Generate TTS -----------------
def generate_voice(quote_text):
    print("🎙️ Generating voice...")
    tts = TTS(model_name="tts_models/en/ljspeech/tacotron2-DDC")
    tts.tts_to_file(text=quote_text, file_path=AUDIO_FILE)
    print("✅ Voice generated.")

# ----------------- Download Video -----------------
def download_video(query):
    print(f"📹 Downloading video for: {query}")
    headers = {"Authorization": PEXELS_API_KEY}
    r = requests.get(f"https://api.pexels.com/videos/search?query={query}&per_page=1", headers=headers).json()
    if not r.get("videos"):
        raise Exception(f"No videos found for {query}")
    url = sorted(r["videos"][0]["video_files"], key=lambda x: x["width"], reverse=True)[0]["link"]
    video_data = requests.get(url).content
    with open(VIDEO_FILE, "wb") as f:
        f.write(video_data)
    print("✅ Video downloaded.")

# ----------------- Create Video with Quote -----------------
def create_video(quote_text):
    print("🎨 Creating video with text overlay...")
    video = VideoFileClip(VIDEO_FILE).subclip(0, 15)  # Shorts max 15 sec
    txt_clip = TextClip(
        quote_text,
        fontsize=50,
        color='white',
        font='Arial-Bold',
        method='caption',
        size=(video.w*0.8, None)
    ).set_position('center').set_duration(video.duration)
    final = CompositeVideoClip([video, txt_clip])
    audio = AudioFileClip(AUDIO_FILE)
    final = final.set_audio(audio)
    final.write_videofile(FINAL_FILE, codec="libx264", audio_codec="aac")
    print("✅ Video ready!")

# ----------------- Upload to YouTube -----------------
def upload_youtube():
    if not YOUTUBE_TOKEN_JSON_B64:
        raise Exception("ERROR: TOKEN_JSON_B64 secret is empty!")
    print("🚀 Uploading to YouTube Shorts...")
    token_json = json.loads(b64decode(YOUTUBE_TOKEN_JSON_B64))
    creds = Credentials.from_authorized_user_info(token_json)
    youtube = build("youtube", "v3", credentials=creds)

    request = youtube.videos().insert(
        part="snippet,status",
        body={
            "snippet": {
                "title": "AI Generated Quote Short",
                "description": "Automatically generated YouTube Shorts with AI quotes",
                "tags": ["ai","quotes","shorts"],
                "categoryId": "27"  # Education / Science & Tech
            },
            "status": {"privacyStatus": "public"}
        },
        media_body=FINAL_FILE
    )
    response = request.execute()
    print("✅ Uploaded Video ID:", response["id"])

# ----------------- Main -----------------
def main():
    try:
        topic, quote = generate_ai_quote()
        print(f"Topic: {topic}\nQuote: {quote}")
        generate_voice(quote)
        download_video(topic)
        create_video(quote)
        upload_youtube()
        print("🎬 All done! Video posted successfully.")
    except Exception as e:
        print("🚨 Bot failed:", e)

if __name__ == "__main__":
    main()
