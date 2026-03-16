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
    concatenate_videoclips,
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
#     max_font capped at 55 → smaller text
# ─────────────────────────────────────────────
def _best_fit(draw, text, font_path, max_w, max_h, max_font=55, min_font=22, spacing=14):
    for font_size in range(max_font, min_font - 1, -2):
        font = ImageFont.truetype(font_path, font_size)
        avg_char_w = font.getlength("A")
        wrap_width = max(10, int((max_w * 0.82) / avg_char_w))
        wrapped = textwrap.fill(text, width=wrap_width)
        bbox = draw.multiline_textbbox((0, 0), wrapped, font=font, spacing=spacing)
        tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
        if tw <= max_w * 0.82 and th <= max_h:
            return font, wrapped, tw, th
    font = ImageFont.truetype(font_path, min_font)
    wrapped = textwrap.fill(text, width=35)
    bbox = draw.multiline_textbbox((0, 0), wrapped, font=font, spacing=spacing)
    return font, wrapped, bbox[2] - bbox[0], bbox[3] - bbox[1]


# ─────────────────────────────────────────────
# 3️⃣  Quote overlay image
#     Box anchored at 3/4 of frame height
# ─────────────────────────────────────────────
def create_quote_image(
    quote_text, size=(1080, 1920),
    font_path="/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
):
    W, H = size
    img  = Image.new("RGBA", size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    # allow the box to occupy at most 20 % of frame height
    max_box_h = int(H * 0.20)
    font, wrapped, tw, th = _best_fit(draw, quote_text, font_path, W, max_box_h)

    pad_x, pad_y = 36, 22
    # anchor top of box at 3/4 of the frame
    box_top = int(H * 0.62)
    box_x0  = (W - tw) // 2 - pad_x
    box_y0  = box_top
    box_x1  = (W + tw) // 2 + pad_x
    box_y1  = box_y0 + th + pad_y * 2

    ov = Image.new("RGBA", size, (0, 0, 0, 0))
    ImageDraw.Draw(ov).rounded_rectangle(
        [box_x0, box_y0, box_x1, box_y1], radius=24, fill=(0, 0, 0, 175)
    )
    img  = Image.alpha_composite(img, ov)
    draw = ImageDraw.Draw(img)
    draw.multiline_text(
        ((W - tw) // 2, box_y0 + pad_y),
        wrapped, font=font, fill="white", align="center", spacing=14,
    )

    path = "/tmp/quote_overlay.png"
    img.save(path)
    return path


# ─────────────────────────────────────────────
# 4️⃣  Author overlay image
#     Sits just below the quote box (≈ 88 % down)
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
    for fs in range(36, 18, -2):          # smaller than before (max 36 px)
        font = ImageFont.truetype(font_path, fs)
        bbox = draw.textbbox((0, 0), text, font=font)
        tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
        if tw <= W * 0.80:
            break

    tx, ty   = (W - tw) // 2, int(H * 0.875)   # sits below quote box
    pad_x, pad_y = 28, 16

    ov = Image.new("RGBA", size, (0, 0, 0, 0))
    ImageDraw.Draw(ov).rounded_rectangle(
        [tx - pad_x, ty - pad_y, tx + tw + pad_x, ty + th + pad_y],
        radius=16, fill=(0, 0, 0, 175),
    )
    img  = Image.alpha_composite(img, ov)
    draw = ImageDraw.Draw(img)
    draw.text((tx, ty), text, font=font, fill=(255, 215, 60))

    path = "/tmp/author_overlay.png"
    img.save(path)
    return path


# ─────────────────────────────────────────────
# 5️⃣  Fetch multiple Pexels video URLs
# ─────────────────────────────────────────────
def get_video_urls(keyword="nature", count=5):
    """Return up to `count` unique mp4 URLs from Pexels."""
    key = os.environ.get("PEXELS_API_KEY")
    if not key:
        print("❌ Missing PEXELS_API_KEY")
        return []
    urls = []
    try:
        r = requests.get(
            "https://api.pexels.com/videos/search",
            headers={"Authorization": key},
            params={"query": keyword, "per_page": min(count * 2, 20), "orientation": "portrait"},
            timeout=10,
        )
        if r.status_code != 200:
            return []
        videos = r.json().get("videos", [])
        random.shuffle(videos)
        for video in videos:
            for f in video["video_files"]:
                if f["file_type"] == "video/mp4":
                    urls.append(f["link"])
                    break
            if len(urls) >= count:
                break
    except Exception as e:
        print(f"⚠️ Pexels error: {e}")
    return urls


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
# 6b️⃣  Build a 15-second composite from multiple clips
# ─────────────────────────────────────────────
def build_15s_clip(keyword, target=15.0):
    """
    Fetch several portrait videos, trim each to a short segment,
    concatenate until we reach `target` seconds, then hard-cut to exactly
    `target` seconds.  Returns a single moviepy clip.
    """

    FALLBACK = "https://filesamples.com/samples/video/mp4/sample_640x360.mp4"
    urls = get_video_urls(keyword, count=6)
    if not urls:
        urls = [FALLBACK]

    clips     = []
    total     = 0.0
    remaining = target

    for url in urls:
        if remaining <= 0:
            break
        try:
            path     = download_video(url)
            raw      = VideoFileClip(path)
            seg_dur  = min(raw.duration, remaining, 6.0)   # each segment ≤ 6 s
            seg      = raw.subclip(0, seg_dur)
            clips.append(seg)
            total    += seg_dur
            remaining = target - total
            print(f"   ✂️  Added {seg_dur:.1f}s clip  (total so far: {total:.1f}s)")
        except Exception as e:
            print(f"   ⚠️  Skipping clip: {e}")

    if not clips:
        raise RuntimeError("No video clips could be loaded.")

    combined = concatenate_videoclips(clips, method="compose")

    # Hard-trim to exactly target seconds
    if combined.duration > target:
        combined = combined.subclip(0, target)

    # Resize all to first clip's dimensions (in case sizes differ)
    W, H = clips[0].w, clips[0].h
    combined = combined.resize((W, H))

    print(f"✅ Combined clip: {combined.duration:.2f}s  @ {W}×{H}")
    return combined


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
    keyword = quote_text.split()[0]

    # Build a 15 s clip from multiple portrait videos
    clip = build_15s_clip(keyword, target=15.0)
    W, H = clip.w, clip.h
    dur  = clip.duration          # ≈ 15 s
    at   = dur - 4.5              # author fades in 4.5 s before end

    # Text overlays
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
