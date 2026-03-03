import os
import random
import tempfile
import textwrap
import datetime
import requests
from moviepy.editor import (
    VideoFileClip,
    ImageClip,
    CompositeVideoClip,
    AudioFileClip,
    CompositeAudioClip
)
from PIL import Image, ImageDraw, ImageFont
from gtts import gTTS

# -------------------------------
# 1️⃣ Get a random quote
# -------------------------------
def get_quote():
    try:
        r = requests.get("https://api.quotable.io/random", timeout=20)
        if r.status_code == 200:
            data = r.json()
            return f"{data['content']} — {data['author']}"
    except Exception:
        print("⚠️ Failed to get quote, using default.")

    default_quotes = [
        " It isn’t normal to know what we want. It is a rare and difficult psychological achievement. — Abraham Maslow",
        "I take my fundamental cue from John Coltrane that says there must be a priority of integrity, honesty, decency, and mastery of craft. — Cornel West",
        "The two most important days in your life are the day you are born... and the day you find out why. — Mark Twain",
        "Death is not the greatest loss in life. The greatest loss is what dies inside us while we live. — Norman Cousins",
        "Liberty means responsibility. That is why most people dread it.” — George Bernard Shaw",
        "If you want to do this, if you want to play big, if you want to really impact lives, you’ve got to face yourself. You’ve got to be courageous and willing to go all in and address everything about you that is uncomfortable. —  Harry Lopez",
        "Life’s most persistent and urgent question is, ‘What are you doing for others?’ — Martin Luther King, Jr",
    ]
    return random.choice(default_quotes)

# -------------------------------
# 2️⃣ Create text overlay image (fits video)
# -------------------------------
def create_text_image(text, size=(1080, 1920), font_path="/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"):
    img = Image.new("RGBA", size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    # Start with a large font and shrink until it fits
    font_size = 100
    while font_size > 20:
        font = ImageFont.truetype(font_path, font_size)
        wrapped_text = textwrap.fill(text, width=25)
        bbox = draw.multiline_textbbox((0, 0), wrapped_text, font=font, spacing=15)
        text_width = bbox[2] - bbox[0]
        text_height = bbox[3] - bbox[1]
        if text_width <= size[0] * 0.9 and text_height <= size[1] * 0.8:
            break
        font_size -= 2

    x = (size[0] - text_width) // 2
    y = (size[1] - text_height) // 2

    draw.multiline_text(
        (x, y),
        wrapped_text,
        font=font,
        fill="white",
        align="center",
        spacing=15,
    )

    path = "/tmp/text_overlay.png"
    img.save(path)
    return path

# -------------------------------
# 3️⃣ Fetch Pexels video
# -------------------------------
def get_video_url(keyword="nature"):
    PEXELS_API_KEY = os.environ.get("PEXELS_API_KEY")
    if not PEXELS_API_KEY:
        print("❌ Missing PEXELS_API_KEY")
        return None

    headers = {"Authorization": PEXELS_API_KEY}
    params = {"query": keyword, "per_page": 10, "orientation": "portrait"}

    try:
        r = requests.get(
            "https://api.pexels.com/videos/search",
            headers=headers,
            params=params,
            timeout=10,
        )
        if r.status_code != 200:
            print("❌ Pexels API failed")
            return None

        data = r.json()
        if not data.get("videos"):
            return None

        video = random.choice(data["videos"])
        for file in video["video_files"]:
            if file["file_type"] == "video/mp4":
                return file["link"]

    except Exception:
        print("⚠️ Error fetching Pexels video")
    return None

# -------------------------------
# 4️⃣ Download video locally
# -------------------------------
def download_video(url):
    print("⬇️ Downloading video...")
    headers = {"User-Agent": "Mozilla/5.0"}
    response = requests.get(url, headers=headers, stream=True, timeout=30)
    if response.status_code != 200:
        raise Exception("Failed to download video")

    temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".mp4")
    for chunk in response.iter_content(chunk_size=1024 * 1024):
        if chunk:
            temp_file.write(chunk)
    temp_file.close()
    print("✅ Video downloaded:", temp_file.name)
    return temp_file.name

# -------------------------------
# 5️⃣ Generate TTS audio
# -------------------------------
def generate_audio(quote):
    tts = gTTS(text=quote, lang='en')
    audio_path = "/tmp/quote_audio.mp3"
    tts.save(audio_path)
    return audio_path

# -------------------------------
# 6️⃣ Create final YouTube Short
# -------------------------------
def create_youtube_short(quote):
    keyword = quote.split()[0]
    video_url = get_video_url(keyword)

    if not video_url:
        video_url = "https://filesamples.com/samples/video/mp4/sample_640x360.mp4"

    local_video_path = download_video(video_url)
    clip = VideoFileClip(local_video_path).subclip(0, 15)

    # Text overlay
    text_img_path = create_text_image(quote, size=(clip.w, clip.h))
    txt_clip = ImageClip(text_img_path).set_duration(clip.duration)
    final_clip = CompositeVideoClip([clip, txt_clip])

    # TTS audio (louder)
    audio_clip = AudioFileClip(generate_audio(quote)).volumex(1.5)

    # Background music from uploaded files (quieter)
    music_files = ["music1.mp3", "music2.mp3", "music3.mp3"]
    music_file = random.choice(music_files)
    music_clip = AudioFileClip(music_file).volumex(0.2).set_duration(clip.duration)

    # Combine TTS and music
    final_audio = CompositeAudioClip([music_clip, audio_clip])
    final_clip = final_clip.set_audio(final_audio)

    output_path = "/tmp/youtube_short.mp4"
    print("🎞 Rendering video...")
    final_clip.write_videofile(
        output_path,
        fps=24,
        codec="libx264",
        audio_codec="aac",
        threads=2,
    )

    print(f"✅ Video saved: {output_path}")
    return output_path

# -------------------------------
# 7️⃣ Upload to YouTube
# -------------------------------
def upload_to_youtube(video_path):
    from google.oauth2.credentials import Credentials
    from googleapiclient.discovery import build
    from googleapiclient.http import MediaFileUpload
    import google.auth.transport.requests

    creds = Credentials(
        None,
        refresh_token=os.environ.get("REFRESH_TOKEN"),
        token_uri="https://oauth2.googleapis.com/token",
        client_id=os.environ.get("CLIENT_ID"),
        client_secret=os.environ.get("CLIENT_SECRET"),
        scopes=["https://www.googleapis.com/auth/youtube.upload"],
    )

    request = google.auth.transport.requests.Request()
    creds.refresh(request)

    youtube = build("youtube", "v3", credentials=creds)

    # Caption with hashtags and current date
    today = datetime.datetime.now().strftime("%Y-%m-%d")
    description = f"#Shorts #Motivation #daily_motivation_quotes - {today}"

    body = {
        "snippet": {
            "title": "Daily Quotes" + description,
            "description": description,
            "tags": ["motivation", "shorts", "daily motivation"],
            "categoryId": "22",
        },
        "status": {"privacyStatus": "public"},
    }

    media = MediaFileUpload(video_path)
    request = youtube.videos().insert(part="snippet,status", body=body, media_body=media)
    response = request.execute()
    print("✅ Uploaded to YouTube!")
    print("Video URL: https://youtube.com/watch?v=" + response["id"])

# -------------------------------
# 8️⃣ Main
# -------------------------------
def main():
    quote = get_quote()
    print(f"💡 Selected quote: {quote}")

    video_path = create_youtube_short(quote)
    upload_to_youtube(video_path)

if __name__ == "__main__":
    main()
