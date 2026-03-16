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
    concatenate_videoclips,
)
from PIL import Image, ImageDraw, ImageFont
from TTS.api import TTS
from pydub import AudioSegment

# -------------------------------
# Voice config: male & female
# -------------------------------
VOICE_OPTIONS = {
    "female": {
        "model": "tts_models/en/ljspeech/tacotron2-DDC",
        "speaker_idx": None,          # single-speaker model
    },
    "male": {
        "model": "tts_models/en/vctk/vits",
        "speaker_idx": "p226",        # VCTK male speaker
    },
}

# -------------------------------
# 1️⃣ Get a random quote
# -------------------------------
def get_quote():
    try:
        r = requests.get("http://api.quotable.io/random", timeout=20)
        if r.status_code == 200:
            data = r.json()
            return data["content"], data["author"]
    except Exception:
        print("⚠️ Failed to get quote, using default.")

    default_quotes = [
        ("It isn't normal to know what we want. It is a rare and difficult psychological achievement.", "Abraham Maslow"),
        ("The two most important days in your life are the day you are born and the day you find out why.", "Mark Twain"),
        ("Death is not the greatest loss in life. The greatest loss is what dies inside us while we live.", "Norman Cousins"),
        ("Liberty means responsibility. That is why most people dread it.", "George Bernard Shaw"),
        ("Life's most persistent and urgent question is, What are you doing for others?", "Martin Luther King Jr."),
    ]
    return random.choice(default_quotes)


# -------------------------------
# 2️⃣  Helper: fit text inside a box
# -------------------------------
def _best_fit(draw, text, font_path, max_w, max_h, max_font=110, min_font=28, spacing=18):
    """Return (font, wrapped_text, text_w, text_h) that fits inside max_w × max_h."""
    for font_size in range(max_font, min_font - 1, -2):
        font = ImageFont.truetype(font_path, font_size)
        # Estimate chars-per-line from average glyph width
        avg_char_w = font.getlength("A")
        wrap_width = max(10, int((max_w * 0.88) / avg_char_w))
        wrapped = textwrap.fill(text, width=wrap_width)
        bbox = draw.multiline_textbbox((0, 0), wrapped, font=font, spacing=spacing)
        tw = bbox[2] - bbox[0]
        th = bbox[3] - bbox[1]
        if tw <= max_w * 0.88 and th <= max_h:
            return font, wrapped, tw, th
    # fallback
    font = ImageFont.truetype(font_path, min_font)
    wrapped = textwrap.fill(text, width=30)
    bbox = draw.multiline_textbbox((0, 0), wrapped, font=font, spacing=spacing)
    return font, wrapped, bbox[2] - bbox[0], bbox[3] - bbox[1]


# -------------------------------
# 3️⃣ Create QUOTE text overlay (no author)
# -------------------------------
def create_quote_image(
    quote_text,
    size=(1080, 1920),
    font_path="/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
):
    """
    Renders only the quote, vertically centred with a semi-transparent
    rounded rectangle behind it so it always stays readable.
    """
    W, H = size
    img = Image.new("RGBA", size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    # Reserve bottom 20 % for the author card that will be composited later
    available_h = int(H * 0.72)
    top_offset  = int(H * 0.10)

    font, wrapped, tw, th = _best_fit(draw, quote_text, font_path, W, available_h)

    pad_x, pad_y = 48, 36
    box_x0 = (W - tw) // 2 - pad_x
    box_y0 = top_offset + (available_h - th) // 2 - pad_y
    box_x1 = (W + tw) // 2 + pad_x
    box_y1 = box_y0 + th + pad_y * 2

    # semi-transparent dark pill
    overlay = Image.new("RGBA", size, (0, 0, 0, 0))
    od = ImageDraw.Draw(overlay)
    od.rounded_rectangle([box_x0, box_y0, box_x1, box_y1], radius=30, fill=(0, 0, 0, 160))
    img = Image.alpha_composite(img, overlay)
    draw = ImageDraw.Draw(img)

    tx = (W - tw) // 2
    ty = box_y0 + pad_y
    draw.multiline_text(
        (tx, ty), wrapped, font=font, fill="white", align="center", spacing=18
    )

    path = "/tmp/quote_overlay.png"
    img.save(path)
    return path


# -------------------------------
# 4️⃣ Create AUTHOR overlay (shown at end)
# -------------------------------
def create_author_image(
    author,
    size=(1080, 1920),
    font_path="/usr/share/fonts/truetype/dejavu/DejaVuSans-BoldOblique.ttf",
):
    """
    Renders '— Author Name' near the bottom of the frame.
    """
    W, H = size
    img = Image.new("RGBA", size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    author_text = f"— {author}"

    # Try font sizes 52 → 28
    for fs in range(52, 27, -2):
        font = ImageFont.truetype(font_path, fs)
        bbox = draw.textbbox((0, 0), author_text, font=font)
        tw = bbox[2] - bbox[0]
        th = bbox[3] - bbox[1]
        if tw <= W * 0.88:
            break

    pad_x, pad_y = 40, 24
    tx = (W - tw) // 2
    ty = int(H * 0.80)          # bottom 20 % area

    overlay = Image.new("RGBA", size, (0, 0, 0, 0))
    od = ImageDraw.Draw(overlay)
    od.rounded_rectangle(
        [tx - pad_x, ty - pad_y, tx + tw + pad_x, ty + th + pad_y],
        radius=20, fill=(0, 0, 0, 170),
    )
    img = Image.alpha_composite(img, overlay)
    draw = ImageDraw.Draw(img)

    draw.text((tx, ty), author_text, font=font, fill=(255, 220, 80))   # golden colour

    path = "/tmp/author_overlay.png"
    img.save(path)
    return path


# -------------------------------
# 5️⃣ Fetch Pexels video
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
            headers=headers, params=params, timeout=10,
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
# 6️⃣ Download video locally
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
# 7️⃣ Generate TTS audio (random male / female)
# -------------------------------
def generate_audio(quote_text, author):
    """Generates speech for the quote + author with a randomly chosen voice."""
    gender = random.choice(["male", "female"])
    voice = VOICE_OPTIONS[gender]
    print(f"🎙️ Using {gender} voice: {voice['model']}")

    # Clean text for TTS
    full_text = f"{quote_text}  ...  {author}".replace("—", "-").replace("…", "...")

    tts = TTS(model_name=voice["model"], progress_bar=False, gpu=False)

    audio_path = "/tmp/quote_audio.wav"
    if voice["speaker_idx"]:
        tts.tts_to_file(text=full_text, file_path=audio_path, speaker=voice["speaker_idx"])
    else:
        tts.tts_to_file(text=full_text, file_path=audio_path)

    return audio_path


# -------------------------------
# 8️⃣ Mix TTS with ASMR background music
# -------------------------------
def combine_with_background(tts_path, background_file, duration):
    voice = AudioSegment.from_file(tts_path)
    background = AudioSegment.from_file(background_file).apply_gain(-25)

    if len(background) < len(voice):
        background = background * ((len(voice) // len(background)) + 1)

    final_audio = voice.overlay(background)

    total_ms = int(duration * 1000)
    if len(final_audio) < total_ms:
        silence = AudioSegment.silent(duration=total_ms - len(final_audio))
        final_audio += silence
    else:
        final_audio = final_audio[:total_ms]

    out_path = "/tmp/final_audio.wav"
    final_audio.export(out_path, format="wav")
    return AudioFileClip(out_path).set_duration(duration)


# -------------------------------
# 9️⃣ Build the final YouTube Short
# -------------------------------
def create_youtube_short(quote_text, author):
    keyword = quote_text.split()[0]
    video_url = get_video_url(keyword)
    if not video_url:
        video_url = "https://filesamples.com/samples/video/mp4/sample_640x360.mp4"

    local_video_path = download_video(video_url)
    clip = VideoFileClip(local_video_path).subclip(0, 15)
    W, H = clip.w, clip.h
    duration = clip.duration           # 15 s
    author_appear_at = duration - 4.5  # author fades in 4.5 s before end

    # ── Quote overlay (visible the whole clip) ──────────────────────────────
    quote_img_path = create_quote_image(quote_text, size=(W, H))
    quote_clip = (
        ImageClip(quote_img_path)
        .set_duration(duration)
    )

    # ── Author overlay (fades in near the end) ──────────────────────────────
    author_img_path = create_author_image(author, size=(W, H))
    author_clip = (
        ImageClip(author_img_path)
        .set_start(author_appear_at)
        .set_duration(duration - author_appear_at)
        .crossfadein(0.8)              # smooth fade-in
    )

    final_clip = CompositeVideoClip([clip, quote_clip, author_clip])

    # ── Audio ────────────────────────────────────────────────────────────────
    tts_audio_path = generate_audio(quote_text, author)

    music_files = ["music1.mp3", "music2.mp3", "music3.mp3"]
    music_file = random.choice(music_files)
    final_audio = combine_with_background(tts_audio_path, music_file, duration)

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
# 🔟 Upload to YouTube
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
   creds.refresh(google.auth.transport.requests.Request())

    youtube = build("youtube", "v3", credentials=creds)
    today = datetime.datetime.now().strftime("%Y-%m-%d")

    body = {
        "snippet": {
            "title": f"The Secret to Success | Daily Motivation {today}",
            "description": f"#Shorts #Motivation #daily_motivation_quotes - {today}",
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
# Main
# -------------------------------
def main():
    quote_text, author = get_quote()
    print(f"💡 Quote : {quote_text}")
    print(f"✍️  Author: {author}")

    video_path = create_youtube_short(quote_text, author)
    upload_to_youtube(video_path)


if __name__ == "__main__":
    main()
