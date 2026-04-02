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
# Voice config  — 100% FREE, no API key needed
#   edge-tts uses Microsoft Azure Neural voices
#   via the Edge browser endpoint (no account).
#   Fallback: Coqui (fully offline)
# ─────────────────────────────────────────────

# Microsoft Azure Neural voices — all free via edge-tts
# Best voices for dramatic motivational narration:
EDGE_VOICES = {
    "male": [
        "en-US-GuyNeural",       # deep, confident — best for motivation
        "en-GB-RyanNeural",      # British narrator, cinematic feel
        "en-US-DavisNeural",     # warm, authoritative
        "en-AU-WilliamNeural",   # strong Australian accent, distinctive
    ],
    "female": [
        "en-US-AriaNeural",      # natural, expressive — most popular
        "en-US-JennyNeural",     # warm, clear
        "en-GB-SoniaNeural",     # calm British female
        "en-US-SaraNeural",      # bright, energetic
    ],
}

# Coqui fallback (offline, no internet needed)
VOICE_COQUI = {
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
        "YOU ARE NOT LAZY.",
        "Most people do not know this about.",
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
# 3b️⃣  Render karaoke frame: all words shown,
#      current word highlighted in yellow
# ─────────────────────────────────────────────
def render_word_highlight_image(
    words, highlight_idx, frame_id, size=(1080, 1920),
    font_path="/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
):
    """
    Draw all words of a segment as wrapped text.
    The word at highlight_idx is rendered in bright yellow;
    spoken words (< highlight_idx) are light-gray;
    upcoming words are white.
    """
    W, H   = size
    text   = " ".join(words)
    img    = Image.new("RGBA", size, (0, 0, 0, 0))
    draw   = ImageDraw.Draw(img)

    max_box_h = int(H * 0.28)
    font_size = 36          # reduced from 44 — cleaner, less cramped
    min_font  = 20
    spacing   = 14

    # Pick font size that fits
    chosen_font = None
    chosen_wrap = text
    for fs in range(font_size, min_font - 1, -2):
        f = ImageFont.truetype(font_path, fs)
        avg_w = f.getlength("A")
        wrap_w = max(8, int((W * 0.82) / avg_w))
        wrapped = textwrap.fill(text, width=wrap_w)
        bbox = draw.multiline_textbbox((0, 0), wrapped, font=f, spacing=spacing)
        if bbox[2] - bbox[0] <= W * 0.82 and bbox[3] - bbox[1] <= max_box_h:
            chosen_font = f
            chosen_wrap = wrapped
            break
    if chosen_font is None:
        chosen_font = ImageFont.truetype(font_path, min_font)
        chosen_wrap = textwrap.fill(text, width=30)

    bbox = draw.multiline_textbbox((0, 0), chosen_wrap, font=chosen_font, spacing=spacing)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]

    pad_x, pad_y = 40, 26
    box_y0 = int(H * 0.60)
    box_x0 = (W - tw) // 2 - pad_x
    box_x1 = (W + tw) // 2 + pad_x
    box_y1 = box_y0 + th + pad_y * 2

    # Dark background box
    ov = Image.new("RGBA", size, (0, 0, 0, 0))
    ImageDraw.Draw(ov).rounded_rectangle(
        [box_x0, box_y0, box_x1, box_y1], radius=28, fill=(0, 0, 0, 190)
    )
    img  = Image.alpha_composite(img, ov)
    draw = ImageDraw.Draw(img)

    # Re-wrap to get line structure, then word-colorize
    lines       = chosen_wrap.split("\n")
    word_cursor = 0                          # index into `words` list
    text_x      = (W - tw) // 2
    cursor_y    = box_y0 + pad_y

    for line in lines:
        line_words   = line.split()
        line_bbox    = draw.textbbox((0, 0), line, font=chosen_font)
        line_w       = line_bbox[2] - line_bbox[0]
        line_x       = (W - line_w) // 2    # center each line individually
        x            = line_x

        for wi, word in enumerate(line_words):
            global_wi = word_cursor + wi

            if global_wi == highlight_idx:
                color = (255, 230, 0)         # bright yellow  — currently spoken
            elif global_wi < highlight_idx:
                color = (180, 180, 180)       # light gray     — already spoken
            else:
                color = (255, 255, 255)       # white          — upcoming

            # Draw stroke then fill
            draw.text((x, cursor_y), word, font=chosen_font,
                      fill=(0, 0, 0), stroke_width=3, stroke_fill=(0, 0, 0))
            draw.text((x, cursor_y), word, font=chosen_font, fill=color)

            word_w = chosen_font.getlength(word + " ")
            x += word_w

        word_cursor += len(line_words)
        line_h = draw.textbbox((0, 0), "Ag", font=chosen_font)[3] + spacing
        cursor_y += line_h

    path = f"/tmp/karaoke_{frame_id:04d}.png"
    img.save(path)
    return path


# ─────────────────────────────────────────────
# 3c️⃣  Build audio-synced karaoke word clips
# ─────────────────────────────────────────────
def build_quote_slides(segments, start_times, durations, size):
    """
    For each segment, split into words and create one ImageClip per word.
    Each word is highlighted in yellow as it is (approximately) spoken,
    while the rest of the segment text stays visible for context.

    Word durations are estimated by sharing the segment duration
    proportionally to each word's character length.
    """
    slides     = []
    frame_id   = 0

    for seg_i, (seg, seg_start, seg_dur) in enumerate(zip(segments, start_times, durations)):
        words = seg.split()
        n     = len(words)
        if n == 0:
            continue

        # Distribute time proportional to word length (longer words take more time)
        char_counts = [max(len(w), 1) for w in words]
        total_chars = sum(char_counts)
        word_durs   = [seg_dur * (c / total_chars) for c in char_counts]

        preview = seg[:50] + ("..." if len(seg) > 50 else "")
        print(f"   📝 Segment {seg_i+1}: [{seg_start:.2f}s → {seg_start+seg_dur:.2f}s]  \"{preview}\"  ({n} words)")

        word_start = seg_start
        for w_i, (word, wdur) in enumerate(zip(words, word_durs)):
            img_path = render_word_highlight_image(words, w_i, frame_id, size=size)
            # NO crossfadein — hard cuts prevent the alpha-bleed flicker that
            # occurs when adjacent clips both have transparency transitions.
            clip = (
                ImageClip(img_path)
                .set_start(word_start)
                .set_duration(wdur)
            )
            slides.append(clip)
            word_start += wdur
            frame_id   += 1

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
# 4b  Fetch author photo from Wikipedia (FREE)
# ─────────────────────────────────────────────
def fetch_author_photo(author_name):
    """
    Query Wikipedia REST API for the author's main image.
    Returns local path to downloaded JPG, or None if not found.
    No API key required — Wikipedia is fully open.
    """
    try:
        # Normalise name for Wikipedia title format
        title = author_name.strip().replace(" ", "_")
        api   = f"https://en.wikipedia.org/api/rest_v1/page/summary/{title}"
        r = requests.get(api, timeout=10,
                         headers={"User-Agent": "YoutubeShortsBot/1.0"})
        if r.status_code != 200:
            print(f"   ℹ️  Wikipedia: no page for '{author_name}'")
            return None

        data     = r.json()
        thumb    = data.get("thumbnail") or data.get("originalimage")
        if not thumb:
            print(f"   ℹ️  Wikipedia: no photo for '{author_name}'")
            return None

        img_url  = thumb["source"]
        img_resp = requests.get(img_url, timeout=15,
                                headers={"User-Agent": "YoutubeShortsBot/1.0"})
        if img_resp.status_code != 200:
            return None

        out = f"/tmp/author_photo_{author_name[:20].replace(' ','_')}.jpg"
        with open(out, "wb") as fh:
            fh.write(img_resp.content)
        print(f"   ✅ Author photo: {out}")
        return out

    except Exception as e:
        print(f"   ⚠️  fetch_author_photo failed: {e}")
        return None


# ─────────────────────────────────────────────
# 4c  Generate thumbnail (1080×1920)
#
#  Layout:
#   ┌──────────────────────────────┐
#   │  Author photo — top 60%      │  ← sharp, colour, slightly darkened
#   │  (face/upper body visible)   │
#   ├──────────────────────────────┤
#   │  Black panel — bottom 40%    │  ← solid dark base for text
#   │   ══ gold accent bar ══      │
#   │   HOOK LINE  (bold, white)   │
#   │   Short quote excerpt        │
#   │   ── thin divider ──         │
#   │   — Author Name (gold)       │
#   └──────────────────────────────┘
#
#  Fallback: if no author photo found, use blurred video frame
#  for the full background instead.
# ─────────────────────────────────────────────
def generate_thumbnail(
    hook, quote_text, author, bg_frame_path,
    size=(1080, 1920),
    bold_font  = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    italic_font= "/usr/share/fonts/truetype/dejavu/DejaVuSans-BoldOblique.ttf",
):
    """
    Build a 1080×1920 thumbnail.
    Primary: author photo (top) + dark text panel (bottom).
    Fallback: blurred video frame full background.
    Returns path to saved PNG.
    """
    import numpy as np
    from PIL import ImageFilter
    import textwrap as tw
    W, H = size

    author_photo_path = fetch_author_photo(author)

    if author_photo_path:
        # ── LAYOUT A: Author photo top 62%, dark panel bottom 38% ────────────
        photo_h = int(H * 0.62)
        panel_h = H - photo_h

        # Load + crop photo to fill the top zone (centre-crop to W×photo_h)
        photo = Image.open(author_photo_path).convert("RGB")
        pw, ph = photo.size
        # Scale so shortest side fits width, preserve aspect ratio
        scale  = max(W / pw, photo_h / ph)
        new_w, new_h = int(pw * scale), int(ph * scale)
        photo  = photo.resize((new_w, new_h), Image.LANCZOS)
        # Centre crop
        left = (new_w - W) // 2
        top  = 0   # show the face (top of image)
        photo = photo.crop((left, top, left + W, top + photo_h))

        # Slightly darken the photo so it feels cinematic, not washed out
        ph_arr = np.array(photo, dtype=np.float32) * 0.78
        photo  = Image.fromarray(ph_arr.clip(0, 255).astype(np.uint8))

        # Soft gradient fade at the BOTTOM of the photo into the dark panel
        fade_h = int(photo_h * 0.28)
        fade   = Image.new("RGBA", (W, photo_h), (0, 0, 0, 0))
        for y in range(photo_h - fade_h, photo_h):
            t     = (y - (photo_h - fade_h)) / fade_h
            alpha = int(255 * (t ** 1.6))
            ImageDraw.Draw(fade).line([(0, y), (W, y)], fill=(0, 0, 0, alpha))
        photo_rgba = photo.convert("RGBA")
        photo_rgba = Image.alpha_composite(photo_rgba, fade)

        # Dark bottom panel
        panel = Image.new("RGB", (W, panel_h), (10, 10, 14))

        # Combine
        canvas = Image.new("RGBA", (W, H))
        canvas.paste(photo_rgba, (0, 0))
        canvas.paste(panel.convert("RGBA"), (0, photo_h))
        draw = ImageDraw.Draw(canvas)

        text_region_top = photo_h + 14   # text starts just below the seam

    else:
        # ── LAYOUT B: Blurred video frame full background (fallback) ──────────
        bg = Image.open(bg_frame_path).convert("RGB").resize((W, H), Image.LANCZOS)
        bg = bg.filter(ImageFilter.GaussianBlur(radius=18))
        bg_arr = np.array(bg, dtype=np.float32) * 0.32
        bg = Image.fromarray(bg_arr.clip(0, 255).astype(np.uint8))

        grad_arr = np.zeros((H, W, 4), dtype=np.uint8)
        for y in range(H):
            alpha = int(210 * (y / H) ** 0.55)
            grad_arr[y, :, 3] = alpha
        grad   = Image.fromarray(grad_arr, "RGBA")
        canvas = bg.convert("RGBA")
        canvas = Image.alpha_composite(canvas, grad)
        draw   = ImageDraw.Draw(canvas)

        text_region_top = int(H * 0.40)

    # ── Gold accent bar ───────────────────────────────────────────────────────
    hook_max_w = int(W * 0.88)
    bar_y = text_region_top + 10
    bar_w = int(W * 0.52)
    bar_x = (W - bar_w) // 2
    draw.rectangle([bar_x, bar_y, bar_x + bar_w, bar_y + 6], fill=(255, 200, 50))

    # ── Hook text (large, bold, white) ────────────────────────────────────────
    hook_y = bar_y + 20
    for fs in range(84, 34, -4):
        f = ImageFont.truetype(bold_font, fs)
        avg_w = f.getlength("A")
        ww    = max(6, int(hook_max_w / avg_w))
        wrapped = tw.fill(hook.upper(), width=ww)
        bbox = draw.multiline_textbbox((0, 0), wrapped, font=f, spacing=8)
        if bbox[2] - bbox[0] <= hook_max_w:
            break
    hook_bbox = draw.multiline_textbbox((0, 0), wrapped, font=f, spacing=8)
    hook_h    = hook_bbox[3] - hook_bbox[1]
    hx = (W - (hook_bbox[2] - hook_bbox[0])) // 2
    draw.multiline_text((hx+3, hook_y+3), wrapped, font=f,
                        fill=(0,0,0,180), spacing=8, align="center")
    draw.multiline_text((hx, hook_y), wrapped, font=f,
                        fill=(255,255,255), stroke_width=3,
                        stroke_fill=(0,0,0), spacing=8, align="center")

    # ── Quote excerpt (first 8 words, smaller grey) ───────────────────────────
    excerpt = " ".join(quote_text.split()[:8])
    if len(quote_text.split()) > 8:
        excerpt += "..."
    ex_y = hook_y + hook_h + 22
    for fs2 in range(38, 20, -2):
        f2 = ImageFont.truetype(bold_font, fs2)
        ww2 = max(8, int(hook_max_w / f2.getlength("A")))
        ex_wrapped = tw.fill(excerpt.upper(), width=ww2)
        bbox2 = draw.multiline_textbbox((0, 0), ex_wrapped, font=f2, spacing=7)
        if bbox2[2] - bbox2[0] <= hook_max_w:
            break
    ex_bbox = draw.multiline_textbbox((0, 0), ex_wrapped, font=f2, spacing=7)
    ex_x = (W - (ex_bbox[2] - ex_bbox[0])) // 2
    draw.multiline_text((ex_x, ex_y), ex_wrapped, font=f2,
                        fill=(195,195,195), stroke_width=2,
                        stroke_fill=(0,0,0), spacing=7, align="center")

    # ── Thin white divider ────────────────────────────────────────────────────
    div_y = ex_y + (ex_bbox[3] - ex_bbox[1]) + 22
    div_w = int(W * 0.28)
    draw.rectangle([(W-div_w)//2, div_y, (W+div_w)//2, div_y+2],
                   fill=(255,255,255,150))

    # ── Author name (gold italic) ─────────────────────────────────────────────
    au_text = f"— {author}"
    au_y    = div_y + 16
    for fs3 in range(36, 20, -2):
        f3 = ImageFont.truetype(italic_font, fs3)
        bbox3 = draw.textbbox((0, 0), au_text, font=f3)
        if bbox3[2] - bbox3[0] <= hook_max_w:
            break
    bbox3 = draw.textbbox((0, 0), au_text, font=f3)
    au_x  = (W - (bbox3[2] - bbox3[0])) // 2
    draw.text((au_x, au_y), au_text, font=f3,
              fill=(255,200,50), stroke_width=2, stroke_fill=(0,0,0))

    out = "/tmp/thumbnail.png"
    canvas.convert("RGB").save(out, quality=97)
    print(f"✅ Thumbnail saved: {out}")
    return out


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
# 7️⃣  TTS — edge-tts (FREE Microsoft Neural)
#         -> Coqui (offline fallback)
#
# Install once:  pip install edge-tts
# No API key, no account, no cost — ever.
# ─────────────────────────────────────────────

import asyncio

# edge-tts rate: "-12%" ≈ SPEECH_RATE 0.88 (slightly slower for clarity)
EDGE_RATE   = "-12%"
EDGE_VOLUME = "+0%"


def _clean_text(text):
    """Strip characters that confuse TTS; end with a clean period."""
    import re
    t = text.replace("\u2014", " ").replace("\u2013", " ").replace("\u2026", " ")
    t = t.replace("\u201c", "").replace("\u201d", "").replace("\u2019", "'")
    t = re.sub(r"[^a-zA-Z0-9 \',\.!\?]", " ", t)
    t = re.sub(r"[\',\.!\?]{2,}", ".", t)
    t = re.sub(r" {2,}", " ", t).strip()
    t = re.sub(r"[\',\.!\? ]+$", "", t) + "."
    return t


def _trim_silence(input_path, output_path, silence_thresh=-45):
    """Trim trailing silence from a WAV using ffmpeg."""
    cmd = [
        "ffmpeg", "-y", "-i", input_path, "-af",
        f"silenceremove=stop_periods=-1:stop_duration=0.3:stop_threshold={silence_thresh}dB",
        output_path,
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        import shutil
        shutil.copy(input_path, output_path)


async def _edge_tts_async(text, mp3_path, voice):
    """Async helper — edge-tts requires async."""
    import edge_tts
    communicate = edge_tts.Communicate(text, voice, rate=EDGE_RATE, volume=EDGE_VOLUME)
    await communicate.save(mp3_path)


def _synth_edge(text, path, voice):
    """
    Synthesise text with Microsoft Azure Neural voice via edge-tts (FREE).
    Saves MP3 -> converts to WAV -> trims silence.
    Returns WAV duration in seconds.
    """
    clean    = _clean_text(text)
    mp3_path = path.replace(".wav", "_edge.mp3")
    trim_path = path.replace(".wav", "_trim.wav")

    # edge-tts is async; run it synchronously
    asyncio.run(_edge_tts_async(clean, mp3_path, voice))

    # MP3 -> WAV
    subprocess.run(
        ["ffmpeg", "-y", "-i", mp3_path, "-ar", "22050", path],
        capture_output=True,
    )

    # Trim trailing silence
    _trim_silence(path, trim_path)
    import shutil
    shutil.move(trim_path, path)

    return len(AudioSegment.from_file(path)) / 1000.0


def _synth_coqui(text, path, tts_engine, speaker):
    """Offline fallback via Coqui TTS (slower, more robotic but no internet needed)."""
    import re, shutil, math
    clean     = _clean_text(text)
    raw_path  = path.replace(".wav", "_raw.wav")
    trim_path = path.replace(".wav", "_trim.wav")
    kw = {"text": clean, "file_path": raw_path}
    if speaker:
        kw["speaker"] = speaker
    tts_engine.tts_to_file(**kw)
    _trim_silence(raw_path, trim_path)

    # Slow down Coqui output to match pacing
    rate   = 0.88
    atempo = f"atempo={rate}"
    cmd    = ["ffmpeg", "-y", "-i", trim_path, "-filter:a", atempo,
              "-ar", "22050", path]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        shutil.copy(trim_path, path)
    return len(AudioSegment.from_file(path)) / 1000.0


def _pick_voice():
    """Pick gender + voice once per video so all segments sound consistent."""
    gender = random.choice(["male", "female"])
    voice  = random.choice(EDGE_VOICES[gender])
    print(f"🎙  Voice: {voice}  (FREE — Microsoft Azure Neural via edge-tts)")
    return gender, voice


def _synth_one(text, path, voice, coqui_cfg):
    """
    Try edge-tts first (free, neural quality).
    Falls back to Coqui if edge-tts fails (e.g. no internet).
    Returns final WAV duration in seconds.
    """
    # 1. edge-tts (free Microsoft Neural voice)
    try:
        dur = _synth_edge(text, path, voice)
        print(f"      via edge-tts  ({dur:.2f}s)")
        return dur
    except Exception as e:
        print(f"   ⚠️  edge-tts failed: {e}")

    # 2. Coqui (offline fallback)
    try:
        tts = TTS(model_name=coqui_cfg["model"], progress_bar=False, gpu=False)
        dur = _synth_coqui(text, path, tts, coqui_cfg["speaker_idx"])
        print(f"      via Coqui offline  ({dur:.2f}s)")
        return dur
    except Exception as e:
        raise RuntimeError(f"All TTS engines failed: {e}")


def generate_audio_segments(segments, author):
    """
    Generate one WAV per segment + author — all FREE, same voice throughout.
    Returns:
        tts_paths : [seg0.wav, seg1.wav, ..., author.wav]
        durations : matching durations in seconds
        PAUSE_MS  : inter-segment silence in milliseconds
    """
    PAUSE_MS = 200
    gender, voice = _pick_voice()
    coqui_cfg     = VOICE_COQUI[gender]

    paths, durs = [], []
    for i, seg in enumerate(segments):
        path = f"/tmp/tts_seg_{i:02d}.wav"
        dur  = _synth_one(seg, path, voice, coqui_cfg)
        paths.append(path)
        durs.append(dur)
        print(f"   🔊 Segment {i+1}: {dur:.2f}s  \"{seg[:50]}\"")

    author_path = "/tmp/tts_author.wav"
    author_dur  = _synth_one(author, author_path, voice, coqui_cfg)
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

    # ── 7. Generate thumbnail from first video frame ─────────────────────────
    first_frame_path = "/tmp/thumb_bg.png"
    clip.save_frame(first_frame_path, t=0.5)   # grab frame at 0.5s
    thumb_path = generate_thumbnail(hook, quote_text, author, first_frame_path,
                                    size=(W, H))

    # ── 8. Composite main video ───────────────────────────────────────────────
    main_video = CompositeVideoClip([clip] + slide_clips + [author_clip])
    main_video = main_video.set_audio(audio_clip)

    # ── 9. Prepend 1-second thumbnail frame ───────────────────────────────────
    #   This makes YouTube's frame selector trivially easy to use.
    #   The thumbnail clip is muted (silent) so audio starts with the quote.
    thumb_clip  = ImageClip(thumb_path).set_duration(1.0)
    silent_1s   = AudioSegment.silent(duration=1000)
    tmp_silence = "/tmp/silence_1s.wav"
    silent_1s.export(tmp_silence, format="wav")
    silence_clip = AudioFileClip(tmp_silence).set_duration(1.0)
    thumb_clip   = thumb_clip.set_audio(silence_clip)

    final = concatenate_videoclips([thumb_clip, main_video], method="compose")

    out = "/tmp/youtube_short.mp4"
    print("🎞 Rendering video...")
    final.write_videofile(out, fps=24, codec="libx264", audio_codec="aac", threads=2)
    print(f"✅ Video saved: {out}")
    return out, thumb_path


# ─────────────────────────────────────────────
# 🔟 Upload to YouTube
# ─────────────────────────────────────────────
def upload_to_youtube(video_path, thumb_path=None):
    from google.oauth2.credentials import Credentials
    from googleapiclient.discovery import build
    from googleapiclient.http import MediaFileUpload
    import google.auth.transport.requests

    # Back to youtube.upload — no scope change needed from the original token.
    # The thumbnail is already baked into frame 0 of the video, so YouTube
    # Studio will offer it in the frame selector automatically.
    creds = Credentials(
        None,
        refresh_token = os.environ.get("REFRESH_TOKEN"),
        token_uri     = "https://oauth2.googleapis.com/token",
        client_id     = os.environ.get("CLIENT_ID"),
        client_secret = os.environ.get("CLIENT_SECRET"),
        scopes        = ["https://www.googleapis.com/auth/youtube.upload"],
    )
    creds.refresh(google.auth.transport.requests.Request())

    youtube = build("youtube", "v3", credentials=creds)
    titles  = [
        "This will hit you hard...",
        "Watch this if you're losing hope",
        "This changed my mindset forever",
        "Don't skip this video",
        "One day you'll understand this",
    ]
    body = {
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
        .insert(part="snippet,status", body=body,
                media_body=MediaFileUpload(video_path, chunksize=-1, resumable=True))
        .execute()
    )
    video_id = resp["id"]
    print(f"✅ Uploaded! https://youtube.com/shorts/{video_id}")
    print("🖼  Thumbnail is frame 0 — go to YouTube Studio > Details > Thumbnail to select it.")

# ─────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────
def main():
    quote_text, author = get_quote()
    print(f"💡 Quote : {quote_text}")
    print(f"✍️  Author: {author}")
    video_path, thumb_path = create_youtube_short(quote_text, author)
    upload_to_youtube(video_path, thumb_path)


if __name__ == "__main__":
    main()
