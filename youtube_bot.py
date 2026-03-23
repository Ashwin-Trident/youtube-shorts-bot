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

# ── Pillow 10+ removed ANTIALIAS; patch it so MoviePy 1.0.3 doesn't crash ──
if not hasattr(Image, "ANTIALIAS"):
    Image.ANTIALIAS = Image.LANCZOS


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
# 1b️⃣  Scroll-stopping hook line
# ─────────────────────────────────────────────
def get_hook():
    hooks = [
        "YOU ARE NOT BEHIND IN LIFE.",
        "READ THIS IF YOU FEEL LOST.",
        "THIS WILL HIT YOU HARD.",
        "YOU NEEDED THIS TODAY.",
        "YOU ARE TRYING YOUR BEST."
    ]
    return random.choice(hooks)


# ─────────────────────────────────────────────
# 2️⃣  Text-fit helper
#     max_font capped at 55 → smaller text
# ─────────────────────────────────────────────
def _best_fit(draw, text, font_path, max_w, max_h, max_font=40, min_font=22, spacing=14):
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
# 3️⃣  Split quote into slide segments
#     Splits on  .  !  ?  and  ,
#     Merges very short fragments with the next one
# ─────────────────────────────────────────────
def split_into_segments(quote_text, min_words=3):
    """
    Split a quote into display segments at every sentence/clause boundary.
    Returns a list of clean strings, each ready to show as one slide.

    Example:
      "Life, a culmination of the past, an awareness of the present."
      -> ["Life, a culmination of the past", "an awareness of the present"]
    """
    import re
    raw      = re.split(r'[.,!?]+', quote_text)
    segments = [s.strip() for s in raw if s.strip()]

    # Merge fragments shorter than min_words into the next segment
    merged, buf = [], ""
    for seg in segments:
        if buf:
            seg = buf + ", " + seg
            buf = ""
        if len(seg.split()) < min_words and seg != segments[-1]:
            buf = seg
        else:
            merged.append(seg)
    if buf:
        if merged:
            merged[-1] += ", " + buf
        else:
            merged.append(buf)

    segments = [s.upper() for s in merged if s]
    return segments if segments else [quote_text.upper()]


# ─────────────────────────────────────────────
# 3b️⃣  Render one segment as a PNG overlay
#      Box sits at 3/4 of the frame height
# ─────────────────────────────────────────────
def render_segment_image(
    text, idx, size=(1080, 1920),
    font_path="/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
):
    W, H = size
    img  = Image.new("RGBA", size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    max_box_h = int(H * 0.22)
    font, wrapped, tw, th = _best_fit(draw, text, font_path, W, max_box_h)

    pad_x, pad_y = 36, 22
    box_top = int(H * 0.62)
    box_x0  = (W - tw) // 2 - pad_x
    box_y0  = box_top
    box_x1  = (W + tw) // 2 + pad_x
    box_y1  = box_y0 + th + pad_y * 2

    ov = Image.new("RGBA", size, (0, 0, 0, 0))
    ImageDraw.Draw(ov).rounded_rectangle(
        [box_x0, box_y0, box_x1, box_y1], radius=24, fill=(0, 0, 0, 180)
    )
    img  = Image.alpha_composite(img, ov)
    draw = ImageDraw.Draw(img)
    draw.multiline_text(
        ((W - tw) // 2, box_y0 + pad_y),
        wrapped, font=font, fill=(255, 255, 255),
        stroke_width=2, stroke_fill=(0, 0, 0),
        align="center", spacing=14,
    )

    path = f"/tmp/segment_{idx:02d}.png"
    img.save(path)
    return path


# ─────────────────────────────────────────────
# 3c️⃣  Build audio-synced fading slide clips
# ─────────────────────────────────────────────
def build_quote_slides(segments, start_times, durations, size, fade=0.30):
    """
    Create one ImageClip per segment timed to its TTS audio.

    Args:
        segments   : list of text strings
        start_times: list of floats — when each slide starts (seconds)
        durations  : list of floats — how long each slide is shown (seconds)
        size       : (W, H) of the video frame
        fade       : crossfade in/out duration
    """
    slides = []
    for i, (seg, start, dur) in enumerate(zip(segments, start_times, durations)):
        img_path = render_segment_image(seg, i, size=size)
        preview  = seg[:50] + ("..." if len(seg) > 50 else "")
        print(f"   📝 Slide {i+1}: [{start:.2f}s → {start+dur:.2f}s]  \"{preview}\"")

        clip = (
            ImageClip(img_path)
            .set_start(start)
            .set_duration(dur)
            .crossfadein(min(fade, dur * 0.3))
            .crossfadeout(min(fade, dur * 0.3))
        )
        slides.append(clip)
    return slides


# ─────────────────────────────────────────────
# 4️⃣  Author overlay image
#     Golden text, sits just below the quote box
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
    for fs in range(36, 18, -2):
        font = ImageFont.truetype(font_path, fs)
        bbox = draw.textbbox((0, 0), text, font=font)
        tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
        if tw <= W * 0.80:
            break

    tx, ty   = (W - tw) // 2, int(H * 0.875)
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
    target_size = None   # set from first successful clip

    for url in urls:
        if remaining <= 0:
            break
        try:
            path    = download_video(url)
            raw     = VideoFileClip(path)
            seg_dur = min(raw.duration, remaining, 6.0)   # each segment ≤ 6 s
            seg     = raw.subclip(0, seg_dur)

            # Lock all clips to the first clip's dimensions
            if target_size is None:
                target_size = (raw.w, raw.h)
            elif (seg.w, seg.h) != target_size:
                seg = seg.resize(target_size)   # ANTIALIAS patch above makes this safe

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

    W, H = target_size
    print(f"✅ Combined clip: {combined.duration:.2f}s  @ {W}×{H}")
    return combined


# ─────────────────────────────────────────────
# 7️⃣  TTS — load once, synthesise per segment
# ─────────────────────────────────────────────
def _load_tts_engine():
    """Pick a random gender, load TTS once, return (tts, speaker_idx)."""
    gender = random.choice(["male", "female"])
    print(f"🎙️ Voice gender: {gender}")
    for label, cfg_map in [("primary", VOICE_PRIMARY), ("fallback", VOICE_FALLBACK)]:
        cfg = cfg_map[gender]
        try:
            print(f"   Trying {label}: {cfg['model']}")
            tts = TTS(model_name=cfg["model"], progress_bar=False, gpu=False)
            print(f"✅ TTS loaded ({label}, {gender})")
            return tts, cfg["speaker_idx"]
        except Exception as e:
            print(f"   ⚠️  {label} failed: {e}")
    raise RuntimeError("❌ All TTS options exhausted.")


# Speaking rate: 0.75 = 75% speed (comfortably slow, easy to follow)
# Range: 0.5 (very slow) → 1.0 (normal) — adjust to taste
SPEECH_RATE = 0.88


def _slow_down(input_path, output_path, rate=SPEECH_RATE):
    """
    Time-stretch a WAV to `rate` speed using ffmpeg atempo filter.
    atempo range is 0.5–2.0; for rates below 0.5 we chain two filters.
    Returns duration of the slowed file in seconds.
    """
    # Build atempo chain: e.g. 0.75 → "atempo=0.75"
    # If rate < 0.5 we need two passes: rate=0.5*0.5=0.25 → "atempo=0.5,atempo=0.5"
    if rate >= 0.5:
        atempo = f"atempo={rate}"
    else:
        # Two-stage: sqrt(rate) each time
        import math
        stage = math.sqrt(rate)
        atempo = f"atempo={stage:.4f},atempo={stage:.4f}"

    cmd = [
        "ffmpeg", "-y", "-i", input_path,
        "-filter:a", atempo,
        "-ar", "22050",    # keep sample rate consistent with TTS output
        output_path
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"   ⚠️  ffmpeg atempo failed, using original: {result.stderr[-200:]}")
        import shutil
        shutil.copy(input_path, output_path)

    return len(AudioSegment.from_file(output_path)) / 1000.0


def _clean_text(text):
    """
    Strip everything the TTS phonemizer can mis-read as extra speech.
    - Remove all characters except letters, digits, spaces, and basic punct
    - Collapse multiple spaces / punctuation
    - Ensure the sentence ends with a single period (gives a clean stop)
    """
    import re
    t = text.replace("—", " ").replace("–", " ").replace("…", " ")
    t = t.replace("\u201c", "").replace("\u201d", "").replace("\u2019", "'")
    # Keep only safe characters
    t = re.sub(r"[^a-zA-Z0-9 ',\.!\?]", " ", t)
    # Collapse runs of spaces / punctuation
    t = re.sub(r"[',\.!\?]{2,}", ".", t)
    t = re.sub(r" {2,}", " ", t).strip()
    # Remove any trailing punctuation then add a clean full stop
    t = re.sub(r"[',\.!\? ]+$", "", t) + "."
    return t


def _trim_silence(input_path, output_path, silence_thresh=-45, min_silence_ms=200):
    """
    Use ffmpeg silenceremove to cut trailing noise/garbage after speech ends.
    Keeps leading audio intact; only trims the tail.
    """
    cmd = [
        "ffmpeg", "-y", "-i", input_path,
        "-af",
        # stop_periods=-1 = trim from the END; stop_threshold in dB
        f"silenceremove=stop_periods=-1:stop_duration=0.3:stop_threshold={silence_thresh}dB",
        output_path,
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        import shutil
        shutil.copy(input_path, output_path)


def _synth(tts, speaker, text, path):
    """
    1. Deep-clean text to stop TTS hallucinating on special chars
    2. Synthesise → raw WAV
    3. Trim trailing silence / noise
    4. Time-stretch to SPEECH_RATE
    Returns duration of the final file in seconds.
    """
    clean    = _clean_text(text)
    raw_path = path.replace(".wav", "_raw.wav")
    trim_path = path.replace(".wav", "_trim.wav")

    kw = {"text": clean, "file_path": raw_path}
    if speaker:
        kw["speaker"] = speaker
    tts.tts_to_file(**kw)

    # Trim trailing noise before slowing down
    _trim_silence(raw_path, trim_path)

    # Slow it down
    return _slow_down(trim_path, path, rate=SPEECH_RATE)


def generate_audio_segments(segments, author):
    """
    Generate one WAV per segment + one for the author, all time-stretched.
    Returns:
        tts_paths : [seg0.wav, seg1.wav, ..., author.wav]
        durations : matching list of floats (seconds)
        PAUSE_MS  : inter-segment silence in ms
    """
    PAUSE_MS = 200   # 0.2 s — faster pacing for better engagement

    tts, speaker = _load_tts_engine()
    paths, durs  = [], []

    for i, seg in enumerate(segments):
        path = f"/tmp/tts_seg_{i:02d}.wav"
        dur  = _synth(tts, speaker, seg, path)
        paths.append(path)
        durs.append(dur)
        print(f"   🔊 Segment {i+1}: {dur:.2f}s  \"{seg[:50]}\"")

    # Author spoken at the end
    author_path = "/tmp/tts_author.wav"
    author_dur  = _synth(tts, speaker, author, author_path)
    paths.append(author_path)
    durs.append(author_dur)
    print(f"   🔊 Author: {author_dur:.2f}s  \"{author}\"")

    return paths, durs, PAUSE_MS


# ─────────────────────────────────────────────
# 8️⃣  Assemble full audio track
# ─────────────────────────────────────────────
def assemble_audio(tts_paths, durations, pause_ms, music_file):
    """
    Concatenate all TTS segments (with short pauses), overlay background
    music, and return (AudioFileClip, total_duration_seconds).
    """
    PAUSE = AudioSegment.silent(duration=pause_ms)
    voice = AudioSegment.empty()

    for path in tts_paths:
        voice += AudioSegment.from_file(path).apply_gain(5) + PAUSE

    total_ms = len(voice)
    total_s  = total_ms / 1000.0

    # Background music — loop to fill, then duck to -18 dB
    bg = AudioSegment.from_file(music_file).apply_gain(-18)
    if len(bg) < total_ms:
        bg = bg * (total_ms // len(bg) + 1)
    bg = bg[:total_ms]

    mixed = voice.overlay(bg)

    out = "/tmp/final_audio.wav"
    mixed.export(out, format="wav")
    print(f"✅ Audio assembled: {total_s:.2f}s")
    return AudioFileClip(out).set_duration(total_s), total_s


# ─────────────────────────────────────────────
# 9️⃣  Build the final YouTube Short
#     Video duration = total TTS audio duration
#     Each slide appears exactly when its audio plays
# ─────────────────────────────────────────────
def create_youtube_short(quote_text, author):
    # keyword = quote_text.split()[0]
    keywords = ["dark", "rain", "alone", "city night", "thinking", "sad"]
    keyword = random.choice(keywords)

    # ── 1. Split quote into segments ────────────────────────────────────────
    hook = get_hook()
    segments = [hook] + split_into_segments(quote_text) + ["READ THAT AGAIN."]
    print(f"📝 {len(segments)} segment(s) detected (incl. hook + loop ending)")

    # ── 2. Generate per-segment TTS → real durations ─────────────────────────
    tts_paths, durations, pause_ms = generate_audio_segments(segments, author)
    pause_s = pause_ms / 1000.0

    # ── 3. Calculate exact start time for each segment slide ─────────────────
    #       Layout: [seg0][pause][seg1][pause]...[segN][pause][author]
    seg_starts  = []   # when each quote segment slide begins
    seg_durs    = []   # display duration of each quote slide
    cursor      = 0.0

    for i, d in enumerate(durations[:-1]):   # all except author
        seg_starts.append(cursor)
        seg_durs.append(d + pause_s)         # slide stays up through the pause
        cursor += d + pause_s

    author_start = cursor
    author_dur   = durations[-1]             # last item is the author
    total_dur    = cursor + author_dur + pause_s

    print(f"⏱  Total duration: {total_dur:.2f}s")
    print(f"   Author appears at: {author_start:.2f}s")

    # ── 4. Build background video to match total_dur ──────────────────────────
    clip = build_15s_clip(keyword, target=total_dur)
    W, H = clip.w, clip.h
    # If audio is longer than video, loop/extend video
    if clip.duration < total_dur:
        from moviepy.editor import vfx
        clip = clip.fx(vfx.loop, duration=total_dur)

    # ── 5. Build synced text slides ───────────────────────────────────────────
    slide_clips = build_quote_slides(segments, seg_starts, seg_durs, size=(W, H))

    author_clip = (
        ImageClip(create_author_image(author, (W, H)))
        .set_start(author_start)
        .set_duration(author_dur + pause_s)
        .crossfadein(0.4)
        .crossfadeout(0.3)
    )

    # ── 6. Assemble audio with background music ───────────────────────────────
    music_file  = random.choice(["music1.mp3", "music2.mp3", "music3.mp3"])
    audio_clip, _ = assemble_audio(tts_paths, durations, pause_ms, music_file)

    # ── 7. Composite and render ───────────────────────────────────────────────
    final = CompositeVideoClip([clip] + slide_clips + [author_clip])
    final = final.set_audio(audio_clip)

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
    titles  = [
        "This will hit you hard...",
        "Watch this if you're losing hope",
        "This changed my mindset forever",
        "Don't skip this video",
        "One day you'll understand this",
    ]
    body    = {
        "snippet": {
            "title":       random.choice(titles),
            "description": "#shorts #motivation #mindset #success #selfimprovement",
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
