import os
import random
import tempfile
import textwrap
from datetime import datetime

import requests
from moviepy.editor import (
    VideoFileClip,
    ImageClip,
    CompositeVideoClip,
    AudioFileClip,
    CompositeAudioClip,
)
from PIL import Image, ImageDraw, ImageFont
from gtts import gTTS

# -------------------------------
# 1️⃣ Get a random quote
# -------------------------------
def get_quote():
    try:
        r = requests.get("https://api.quotable.io/random", timeout=10)
        if r.status_code == 200:
            data = r.json()
            return data["content"], data["author"]
    except Exception:
        print("⚠️ Failed to get quote, using default.")
    default_quotes = [
        ("Angaad poo engad poo.. pattullaa nnu paranja pattoolaa", "Aysha Gunda"),
         ("Angaad poo engad poo.. pattullaa nnu paranja pattoolaa", "Aysha Gunda")
    ]
    return random.choice(default_quotes)

# -------------------------------
# 2️⃣ Create text overlay image
# -------------------------------
def create_text_image(text, size=(1080, 1920), font_size=80):
    img = Image.new("RGBA", size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    font = ImageFont.truetype(
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", font_size
    )
    wrapped_text = textwrap.fill(text, width=25)
    bbox = draw.multiline_textbbox((0, 0), wrapped_text, font=font, spacing=20)
    text_width = bbox[2] - bbox[0]
    text_height = bbox[3] - bbox[1]
    x = (size[0] - text_width) // 2
    y = (size[1] - text_height) // 2
    draw.multiline_text(
        (x, y),
        wrapped_text,
        font=font,
        fill="white",
        align="center",
        spacing=20,
    )
    path = "/tmp/text_overlay.png"
    img.save(path)
    return path

# -------------------------------
# 3️⃣ Pick random video from Pexels
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
def generate_audio(text):
    tts = gTTS(text=text, lang='en')
    audio_path = "/tmp/quote_audio.mp3"
    tts.save(audio_path)
    return audio_path

# -------------------------------
# 6️⃣ Pick random local music
# -------------------------------
def pick_local_music():
    local_music_files = ["music1.mp3", "music2.mp3", "music3.mp3"]
    music_file = random.choice(local_music_files)
    if os.path.exists(music_file):
        return music_file
    return None

# -------------------------------
# 7️⃣ Create final YouTube Short
# -------------------------------
def create_youtube_short(quote, author):
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

    # TTS audio
    tts_audio_clip = AudioFileClip(generate_audio(quote)).volumex(1.0)

    # Background music
    music_file = pick_local_music()
    if music_file:
        music_clip = AudioFileClip(music_file).volumex(0.05).set_duration(clip.duration)
        final_audio = CompositeAudioClip([tts_audio_clip, music_clip])
    else:
        final_audio = tts_audio_clip

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
# 8️⃣ YouTube caption
# -------------------------------
def generate_caption():
    today = datetime.now().strftime("%Y-%m-%d")
    return f"#Shorts #Motivation #daily_motivation_quotes - {today}"

# -------------------------------
# 9️⃣ Main
# -------------------------------
def main():
    quote, author = get_quote()
    print(f"💡 Selected quote: {quote} — {author}")

    video_path = create_youtube_short(quote, author)
    caption = generate_caption()

    print("🎬 Video ready!")
    print("Caption:", caption)
    print("File path:", video_path)

if __name__ == "__main__":
    main()
