import os
import subprocess
import sys
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
)
from PIL import Image, ImageDraw, ImageFont
from TTS.api import TTS
from pydub import AudioSegment


# ─────────────────────────────────────────────
# 0️⃣  System dependency check (espeak-ng)
# ─────────────────────────────────────────────
def ensure_espeak():
    """Install espeak-ng automatically if missing."""
    try:
        result = subprocess.run(
            ["espeak-ng", "--version"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        if result.returncode == 0:
            print("✅ espeak-ng already installed.")
            return
    except FileNotFoundError:
        pass

    print("📦 espeak-ng not found — installing...")
    ret = subprocess.run(
        ["sudo", "apt-get", "install", "-y", "espeak-ng"],
        capture_output=True, text=True,
    )
    if ret.returncode != 0:
        print("⚠️  apt-get failed, trying apt...")
        subprocess.run(["sudo", "apt", "install", "-y", "espeak-ng"], check=True)
    print("✅ espeak-ng installed successfully.")


ensure_espeak()   # always runs before any TTS import/usage


# ─────────────────────────────────────────────
# Voice config: male & female (with fallbacks)
# ─────────────────────────────────────────────
VOICE_PRIMARY = {
    "female": {"model": "tts_models/en/ljspeech/tacotron2-DDC", "speaker_idx": None},
    "male":   {"model": "tts_models/en/vctk/vits",              "speaker_idx": "p226"},
}

# fallback models that do NOT require espeak-ng
VOICE_FALLBACK = {
    "female": {"model": "tts_models/en/ljspeech/tacotron2-DDC", "speaker_idx": None},
    "male":   {"model": "tts_models/en/ljspeech/glow-tts",      "speaker_idx": None},
}


# ─────────────────────────────────────────────
# 1️⃣  Get a random quote
# ─────────────────────────────────────────────
def get_quote():
    try:
        r = requests.get("http://api.quotable.io/random", timeout=20)
        if r.status_code == 200:
            d = r.json()
            return d["content"], d["author"]
    except Exception:
        print("⚠️ Quotable API failed, using default.")

    defaults = [
        ("It isn't normal to know what we want. It is a rare and difficult psychological achievement.", "Abraham Maslow"),
        ("The two most important days in your life are the day you are born and the day you find out why.", "Mark Twain"),
        ("Death is not the greatest loss in life. The greatest loss is what dies inside us while we live.", "Norman Cousins"),
        ("Liberty means responsibility. That is why most people dread it.", "George Bernard Shaw"),
        ("Life's most persistent and urgent question is, What are you doing for others?", "Martin Luther King Jr."),
    ]
    return random.choice(defaults)


# ─────────────────────────────────────────────
# 2️⃣  Text-fit helper
# ─────────────────────────────────────────────
def _best_fit(draw, text, font_path, max_w, max_h, max_font=110, min_font=28, spacing=18):
    for font_size in range(max_font, min_font - 1, -2):
        font = ImageFont.truetype(font_path, font_size)
        avg_char_w = font.getlength("A")
        wrap_width = max(10, int((max_w * 0.88) / avg_char_w))
        wrapped = textwrap.fill(text, width=wrap_width)
        bbox = draw.multiline_textbbox((0, 0), wrapped, font=font, spacing=spacing)
        tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
        if tw <= max_w * 0.88 and th <= max_h:
            return font, wrapped, tw, th
    font = ImageFont.truetype(font_path, min_font)
    wrapped = textwrap.fill(text, width=30)
    bbox = draw.multiline_textbbox((0, 0), wrapped, font=font, spacing=spacing)
    return font, wrapped, bbox[2] - bbox[0], bbox[3] - bbox[1]


# ─────────────────────────────────────────────
# 3️⃣  Quote overlay image
# ─────────────────────────────────────────────
def create_quote_image(
    quote_text, size=(1080, 1920),
    font_path="/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
):
    W, H = size
    img  = Image.new("RGBA", size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    available_h = int(H * 0.72)
    top_offset  = int(H * 0.10)
    font, wrapped, tw, th = _best_fit(draw, quote_text, font_path, W, available_h)

    pad_x, pad_y = 48, 36
    box_x0 = (W - tw) // 2 - pad_x
    box_y0 = top_offset + (available_h - th) // 2 - pad_y
    box_x1 = (W + tw) // 2 + pad_x
    box_y1 = box_y0 + th + pad_y * 2

    ov = Image.new("RGBA", size, (0, 0, 0, 0))
    ImageDraw.Draw(ov).rounded_rectangle([box_x0, box_y0, box_x1, box_y1], radius=30, fill=(0, 0, 0, 160))
    img  = Image.alpha_composite(img, ov)
    draw = ImageDraw.Draw(img)
    draw.multiline_text(((W - tw) // 2, box_y0 + pad_y), wrapped, font=font, fill="white", align="center", spacing=18)

    path = "/tmp/quote_overlay.png"
    img.save(path)
    return path


# ─────────────────────────────────────────────
# 4️⃣  Author overlay image (shown at end)
# ─────────────────────────────────────────────
def create_author_image(
    author, size=(1080, 1920),
    font_path="/usr/share/fonts/truetype/dejavu/DejaVuSans-BoldOblique.ttf",
):
    W, H  = size
    img   = Image.new("RGBA", size, (0, 0, 0, 0))
    draw  = ImageDraw.Draw(img)
    text  = f"— {author}"
    tw = th = 0
    font  = None
    for fs in range(52, 27, -2):
        font = ImageFont.truetype(font_path, fs)
        bbox = draw.textbbox((0, 0), text, font=font)
        tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
        if tw <= W * 0.88:
            break

    tx, ty   = (W - tw) // 2, int(H * 0.80)
    pad_x, pad_y = 40, 24

    ov = Image.new("RGBA", size, (0, 0, 0, 0))
    ImageDraw.Draw(ov).rounded_rectangle(
        [tx - pad_x, ty - pad_y, tx + tw + pad_x, ty + th + pad_y],
        radius=20, fill=(0, 0, 0, 170),
    )
    img  = Image.alpha_composite(img, ov)
    draw = ImageDraw.Draw(img)
    draw.text((tx, ty), text, font=font, fill=(255, 220, 80))

    path = "/tmp/author_overlay.png"
    img.save(path)
    return path


# ─────────────────────────────────────────────
# 5️⃣  Fetch Pexels video URL
# ─────────────────────────────────────────────
def get_video_url(keyword="nature"):
    key = os.environ.get("PEXELS_API_KEY")
    if not key:
        print("❌ Missing PEXELS_API_KEY")
        return None
    try:
        r = requests.get(
            "https://api.pexels.com/videos/search",
            headers={"Authorization": key},
            params={"query": keyword, "per_page": 10, "orientation": "portrait"},
            timeout=10,
        )
        if r.status_code != 200:
            return None
        videos = r.json().get("videos")
        if not videos:
            return None
        for f in random.choice(videos)["video_files"]:
            if f["file_type"] == "video/mp4":
                return f["link"]
    except Exception as e:
        print(f"⚠️ Pexels error: {e}")
    return None


# ─────────────────────────────────────────────
# 6️⃣  Download video locally
# ─────────────────────────────────────────────
def download_video(url):
    print("⬇️ Downloading video...")
    resp = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, stream=True, timeout=30)
    if resp.status_code != 200:
        raise Exception("Failed to download video")
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".mp4")
    for chunk in resp.iter_content(chunk_size=1024 * 1024):
        if chunk:
            tmp.write(chunk)
    tmp.close()
    print("✅ Video downloaded:", tmp.name)
    return tmp.name


# ─────────────────────────────────────────────
# 7️⃣  TTS audio — random gender with fallback
# ─────────────────────────────────────────────
def generate_audio(quote_text, author):
    gender    = random.choice(["male", "female"])
    full_text = f"{quote_text}. {author}.".replace("—", "-").replace("…", "...")
    audio_out = "/tmp/quote_audio.wav"

    print(f"🎙️ Voice gender: {gender}")

    for label, cfg_map in [("primary", VOICE_PRIMARY), ("fallback", VOICE_FALLBACK)]:
        cfg = cfg_map[gender]
        try:
            print(f"   Trying {label}: {cfg['model']}")
            tts = TTS(model_name=cfg["model"], progress_bar=False, gpu=False)
            kw  = {"text": full_text, "file_path": audio_out}
            if cfg["speaker_idx"]:
                kw["speaker"] = cfg["speaker_idx"]
            tts.tts_to_file(**kw)
            print(f"✅ Audio OK ({label}, {gender})")
            return audio_out
        except Exception as e:
            print(f"   ⚠️  {label} failed: {e}")

    raise RuntimeError("❌ All TTS options exhausted.")


# ─────────────────────────────────────────────
# 8️⃣  Mix TTS with background music
# ─────────────────────────────────────────────
def combine_with_background(tts_path, music_file, duration):
    voice = AudioSegment.from_file(tts_path)
    bg    = AudioSegment.from_file(music_file).apply_gain(-25)

    if len(bg) < len(voice):
        bg = bg * ((len(voice) // len(bg)) + 1)

    mixed    = voice.overlay(bg)
    total_ms = int(duration * 1000)

    if len(mixed) < total_ms:
        mixed += AudioSegment.silent(duration=total_ms - len(mixed))
    else:
        mixed = mixed[:total_ms]

    out = "/tmp/final_audio.wav"
    mixed.export(out, format="wav")
    return AudioFileClip(out).set_duration(duration)


# ─────────────────────────────────────────────
# 9️⃣  Build the final YouTube Short
# ─────────────────────────────────────────────
def create_youtube_short(quote_text, author):
    url  = get_video_url(quote_text.split()[0]) or "https://filesamples.com/samples/video/mp4/sample_640x360.mp4"
    clip = VideoFileClip(download_video(url)).subclip(0, 15)
    W, H = clip.w, clip.h
    dur  = clip.duration          # 15 s
    at   = dur - 4.5              # author appears 4.5 s before end

    quote_clip  = ImageClip(create_quote_image(quote_text, (W, H))).set_duration(dur)
    author_clip = (
        ImageClip(create_author_image(author, (W, H)))
        .set_start(at)
        .set_duration(dur - at)
        .crossfadein(0.8)
    )

    final = CompositeVideoClip([clip, quote_clip, author_clip])
    audio = combine_with_background(
        generate_audio(quote_text, author),
        random.choice(["music1.mp3", "music2.mp3", "music3.mp3"]),
        dur,
    )
    final = final.set_audio(audio)

    out = "/tmp/youtube_short.mp4"
    print("🎞 Rendering video...")
    final.write_videofile(out, fps=24, codec="libx264", audio_codec="aac", threads=2)
    print(f"✅ Video saved: {out}")
    return out


# ─────────────────────────────────────────────
# 🔟 Upload to YouTube
# ─────────────────────────────────────────────
def upload_to_youtube(video_path):
    from google.oauth2.credentials import Credentials
    from googleapiclient.discovery import build
    from googleapiclient.http import MediaFileUpload
    import google.auth.transport.requests

    creds = Credentials(
        None,
        refresh_token   = os.environ.get("REFRESH_TOKEN"),
        token_uri       = "https://oauth2.googleapis.com/token",
        client_id       = os.environ.get("CLIENT_ID"),
        client_secret   = os.environ.get("CLIENT_SECRET"),
        scopes          = ["https://www.googleapis.com/auth/youtube.upload"],
    )
    creds.refresh(google.auth.transport.requests.Request())

    youtube = build("youtube", "v3", credentials=creds)
    today   = datetime.datetime.now().strftime("%Y-%m-%d")
    body    = {
        "snippet": {
            "title":       f"The Secret to Success | Daily Motivation {today}",
            "description": f"#Shorts #Motivation #daily_motivation_quotes - {today}",
            "tags":        ["motivation", "shorts", "daily motivation"],
            "categoryId":  "22",
        },
        "status": {"privacyStatus": "public"},
    }

    resp = (
        youtube.videos()
        .insert(part="snippet,status", body=body, media_body=MediaFileUpload(video_path))
        .execute()
    )
    print("✅ Uploaded! https://youtube.com/watch?v=" + resp["id"])


# ─────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────
def main():
    quote_text, author = get_quote()
    print(f"💡 Quote : {quote_text}")
    print(f"✍️  Author: {author}")
    upload_to_youtube(create_youtube_short(quote_text, author))


if __name__ == "__main__":
    main()
