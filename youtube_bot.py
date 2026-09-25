"""
youtube_bot.py  —  YouTube Shorts Bot
"""

import os
import subprocess
import sys
import random
import tempfile
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

from quote_status import (
    LANGUAGES, get_next_quote, get_quote_by_id, get_pending, mark_posted, reset_all, show_status,
    last_posted_at, pending_count, quotes_file,
)

if not hasattr(Image, "ANTIALIAS"):
    Image.ANTIALIAS = Image.LANCZOS


# ─────────────────────────────────────────────
# 0️⃣  espeak-ng check
# ─────────────────────────────────────────────
def ensure_espeak():
    try:
        result = subprocess.run(["espeak-ng", "--version"],
                                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        if result.returncode == 0:
            print("✅ espeak-ng already installed.")
            return
    except FileNotFoundError:
        pass
    print("📦 espeak-ng not found — installing...")
    ret = subprocess.run(["sudo", "apt-get", "install", "-y", "espeak-ng"],
                         capture_output=True, text=True)
    if ret.returncode != 0:
        subprocess.run(["sudo", "apt", "install", "-y", "espeak-ng"], check=True)
    print("✅ espeak-ng installed successfully.")

ensure_espeak()


# ─────────────────────────────────────────────
# Voice config
# ─────────────────────────────────────────────
EDGE_VOICES = {
    "male":   ["en-US-GuyNeural", "en-GB-RyanNeural", "en-US-DavisNeural", "en-AU-WilliamNeural"],
    "female": ["en-US-AriaNeural", "en-US-JennyNeural", "en-GB-SoniaNeural", "en-US-SaraNeural"],
}
VOICE_COQUI = {
    "female": {"model": "tts_models/en/ljspeech/tacotron2-DDC", "speaker_idx": None},
    "male":   {"model": "tts_models/en/ljspeech/glow-tts",      "speaker_idx": None},
}

BOLD_FONT   = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
ITALIC_FONT = "/usr/share/fonts/truetype/dejavu/DejaVuSans-BoldOblique.ttf"
if not os.path.exists(ITALIC_FONT):
    ITALIC_FONT = BOLD_FONT
# Needs the fonts-noto-core apt package (installed by the workflow)
MALAYALAM_FONT = "/usr/share/fonts/truetype/noto/NotoSansMalayalam-Bold.ttf"


# ─────────────────────────────────────────────
# Per-language settings
# ─────────────────────────────────────────────
LANG_CONFIG = {
    "en": {
        "voices":        EDGE_VOICES,
        "hooks":         ["{a} said this.", "Listen to {a}.", "Remember what {a} said.",
                          "{a} knew this.", "Words from {a}."],
        "ending":        "READ THAT AGAIN.",
        "caption_font":  BOLD_FONT,
        "author_font":   ITALIC_FONT,
        "caption_chars": 16,
        "line_spacing":  1.22,
        "uppercase":     True,
        "hashtags":      "#shorts #motivation #sportsmotivation #mindset #quotes #dailymotivation",
        "tags":          ["motivation", "shorts", "sports motivation", "quotes",
                          "motivational quotes", "mindset"],
        "kind":          "quote",
        "yt_language":   "en",
        "category":      "17",   # Sports
    },
    "ml": {
        "voices":        {"male": ["ml-IN-MidhunNeural"], "female": ["ml-IN-SobhanaNeural"]},
        # "{a} പറഞ്ഞത് കേൾക്കൂ." = "Listen to what {a} said."
        # "{a} പറഞ്ഞത് ഓർക്കുക." = "Remember what {a} said."
        "hooks":         ["{a} പറഞ്ഞത് കേൾക്കൂ.", "{a} പറഞ്ഞത് ഓർക്കുക."],
        "ending":        "ഒന്നുകൂടി വായിക്കൂ.",   # "Read it once more."
        "caption_font":  MALAYALAM_FONT,
        "author_font":   MALAYALAM_FONT,
        "caption_chars": 24,     # Malayalam words are long in code points
        "line_spacing":  1.55,   # room for Malayalam vowel signs above/below
        "uppercase":     False,
        "hashtags":      "#shorts #malayalam #malayalammotivation #motivation "
                         "#sportsmotivation #malayalamquotes",
        "tags":          ["malayalam", "malayalam motivation", "malayalam quotes",
                          "motivation malayalam", "shorts", "sports motivation"],
        "kind":          "quote",
        "yt_language":   "ml",
        "category":      "17",   # Sports
    },
    "ml_facts": {
        "voices":        {"male": ["ml-IN-MidhunNeural"], "female": ["ml-IN-SobhanaNeural"]},
        # "നിങ്ങൾക്കറിയാമോ?"          = "Did you know?"
        # "ഇത് അധികമാർക്കും അറിയില്ല." = "Not many people know this."
        # "ഇത് കേട്ടാൽ നിങ്ങൾ ഞെട്ടും." = "This will shock you."
        "hooks":         ["നിങ്ങൾക്കറിയാമോ?", "ഇത് അധികമാർക്കും അറിയില്ല.",
                          "ഇത് കേട്ടാൽ നിങ്ങൾ ഞെട്ടും."],
        # "Follow for more facts like this."
        "ending":        "ഇതുപോലുള്ള കൂടുതൽ അറിവുകൾക്ക് ഫോളോ ചെയ്യൂ.",
        "caption_font":  MALAYALAM_FONT,
        "author_font":   MALAYALAM_FONT,
        "caption_chars": 24,
        "line_spacing":  1.55,
        "uppercase":     False,
        "hashtags":      "#shorts #malayalam #facts #malayalamfacts #didyouknow #science",
        "tags":          ["malayalam", "malayalam facts", "facts", "did you know",
                          "interesting facts", "science", "shorts"],
        "kind":          "fact",
        "yt_language":   "ml",
        "category":      "28",   # Science & Technology
    },
}

# ─────────────────────────────────────────────
# Facts: on-screen topic label + fallback footage
# Each fact Short covers up to FACTS_PER_VIDEO facts on one topic
# (~25-30s: a numbered list keeps people watching to the end).
# ─────────────────────────────────────────────
FACTS_PER_VIDEO = 3
ML_NUMBERS = {1: "ഒന്ന്", 2: "രണ്ട്", 3: "മൂന്ന്", 4: "നാല്", 5: "അഞ്ച്"}


def fact_items(fact, lang):
    """The chosen fact plus the next pending facts on the same topic."""
    others = [f for f in get_pending(lang)
              if f["topic"] == fact["topic"] and f["id"] != fact["id"]]
    return [fact] + others[:FACTS_PER_VIDEO - 1]


def fact_list_hook(topic, n):
    """e.g. "ബഹിരാകാശത്തെ കുറിച്ച് അധികമാർക്കും അറിയാത്ത മൂന്ന് കാര്യങ്ങൾ."
    = "Three things most people don't know about space." """
    return f"{topic['about']} അധികമാർക്കും അറിയാത്ത {ML_NUMBERS[n]} കാര്യങ്ങൾ."

FACT_TOPICS = {
    # "galaxy" alone finds Samsung phones on stock sites, so every space
    # search says "space"/"night sky" explicitly.
    "space":   {"label": "ബഹിരാകാശം",        # Space
                "about": "ബഹിരാകാശത്തെ കുറിച്ച്",   # about space
                "keywords": ["galaxy space", "milky way night sky", "nebula space",
                             "stars universe", "outer space"],
                "nasa": ["galaxy", "hubble galaxy", "milky way", "nebula", "webb galaxy"]},
    "aliens":  {"label": "അന്യഗ്രഹ ജീവൻ",      # Alien life
                "about": "അന്യഗ്രഹ ജീവനെ കുറിച്ച്",  # about alien life
                "keywords": ["outer space", "milky way night sky", "radio telescope",
                             "galaxy space"],
                "nasa": ["exoplanet", "europa", "galaxy", "hubble"]},
    "animals": {"label": "ജീവലോകം",           # The living world
                "about": "ജീവികളെ കുറിച്ച്",         # about animals
                "keywords": ["underwater", "wildlife", "ocean"]},
    "body":    {"label": "മനുഷ്യശരീരം",        # Human body
                "about": "നമ്മുടെ ശരീരത്തെ കുറിച്ച്",  # about our body
                "keywords": ["human body", "science laboratory", "microscope"]},
    "earth":   {"label": "നിങ്ങൾക്കറിയാമോ?",   # Did you know?
                "about": "ഈ ലോകത്തെ കുറിച്ച്",       # about this world
                "keywords": ["earth from space", "nature landscape", "storm clouds"]},
}


# ─────────────────────────────────────────────
# Author → sport + gender
# Drives the background footage (their sport, not random mood clips),
# the narrator voice (matches the author) and the hashtags.
# ─────────────────────────────────────────────
SPORT_KEYWORDS = {
    "basketball":   ["basketball dunk", "basketball court", "basketball training"],
    "soccer":       ["soccer", "soccer training", "football stadium"],
    "boxing":       ["boxing", "boxing training", "punching bag"],
    "tennis":       ["tennis", "tennis court", "tennis player"],
    "athletics":    ["sprinter", "running track", "athlete running"],
    "running":      ["marathon running", "runner road", "running track"],
    "swimming":     ["swimmer", "swimming pool", "swimming race"],
    "golf":         ["golf", "golf swing", "golf course"],
    "hockey":       ["ice hockey", "ice skating", "hockey"],
    "baseball":     ["baseball", "baseball stadium", "baseball batting"],
    "football":     ["american football", "football field", "football training"],
    "cricket":      ["cricket", "cricket stadium", "cricket batting"],
    "racing":       ["race car", "racing track", "car racing"],
    "martial arts": ["martial arts", "karate training", "kickboxing"],
    "mma":          ["mma", "boxing training", "fighter training"],
    "gymnastics":   ["gymnastics", "gymnast", "gymnastics training"],
    "wrestling":    ["wrestling", "gym workout", "athlete training"],
    "gym":          ["gym workout", "weightlifting", "bodybuilding"],
}
DEFAULT_SPORT_KEYWORDS = ["athlete training", "gym workout", "running track"]

AUTHOR_PROFILES = {
    "Michael Jordan": ("basketball", "male"),       "LeBron James": ("basketball", "male"),
    "Kobe Bryant": ("basketball", "male"),          "Stephen Curry": ("basketball", "male"),
    "Magic Johnson": ("basketball", "male"),        "Larry Bird": ("basketball", "male"),
    "Kareem Abdul-Jabbar": ("basketball", "male"),  "Bill Russell": ("basketball", "male"),
    "Kevin Garnett": ("basketball", "male"),        "Tim Duncan": ("basketball", "male"),
    "Giannis Antetokounmpo": ("basketball", "male"), "John Wooden": ("basketball", "male"),
    "Pat Riley": ("basketball", "male"),            "Phil Jackson": ("basketball", "male"),
    "Jim Valvano": ("basketball", "male"),
    "Cristiano Ronaldo": ("soccer", "male"),        "Lionel Messi": ("soccer", "male"),
    "Pele": ("soccer", "male"),                     "Mia Hamm": ("soccer", "female"),
    "Muhammad Ali": ("boxing", "male"),             "Mike Tyson": ("boxing", "male"),
    "Conor McGregor": ("mma", "male"),              "Bruce Lee": ("martial arts", "male"),
    "Serena Williams": ("tennis", "female"),        "Roger Federer": ("tennis", "male"),
    "Rafael Nadal": ("tennis", "male"),             "Billie Jean King": ("tennis", "female"),
    "Martina Navratilova": ("tennis", "female"),    "Arthur Ashe": ("tennis", "male"),
    "Usain Bolt": ("athletics", "male"),            "Carl Lewis": ("athletics", "male"),
    "Jesse Owens": ("athletics", "male"),           "Wilma Rudolph": ("athletics", "female"),
    "Jackie Joyner-Kersee": ("athletics", "female"),
    "Roger Bannister": ("running", "male"),         "Steve Prefontaine": ("running", "male"),
    "Eliud Kipchoge": ("running", "male"),
    "Michael Phelps": ("swimming", "male"),         "Tiger Woods": ("golf", "male"),
    "Wayne Gretzky": ("hockey", "male"),
    "Babe Ruth": ("baseball", "male"),              "Jackie Robinson": ("baseball", "male"),
    "Derek Jeter": ("baseball", "male"),            "Hank Aaron": ("baseball", "male"),
    "Yogi Berra": ("baseball", "male"),
    "Vince Lombardi": ("football", "male"),         "Lou Holtz": ("football", "male"),
    "Tom Landry": ("football", "male"),             "Walter Payton": ("football", "male"),
    "Sachin Tendulkar": ("cricket", "male"),        "MS Dhoni": ("cricket", "male"),
    "Virat Kohli": ("cricket", "male"),
    "Ayrton Senna": ("racing", "male"),             "Michael Schumacher": ("racing", "male"),
    "Mario Andretti": ("racing", "male"),
    "Simone Biles": ("gymnastics", "female"),       "Nadia Comaneci": ("gymnastics", "female"),
    "Dan Gable": ("wrestling", "male"),             "Dwayne Johnson": ("wrestling", "male"),
    "Arnold Schwarzenegger": ("gym", "male"),
}


def author_profile(author):
    """Return (sport, gender) for an author; unknown authors get generic footage."""
    if author in AUTHOR_PROFILES:
        return AUTHOR_PROFILES[author]
    print(f"   ℹ️  '{author}' not in AUTHOR_PROFILES — using generic athlete footage")
    return None, random.choice(["male", "female"])


# ─────────────────────────────────────────────
# 1️⃣  Get a quote
# ─────────────────────────────────────────────
def pick_language():
    """
    Language for this run: --lang / BOT_LANGUAGE override, otherwise alternate —
    whichever language was posted least recently goes next.
    """
    forced = None
    if "--lang" in sys.argv:
        forced = sys.argv[sys.argv.index("--lang") + 1]
    elif os.environ.get("BOT_LANGUAGE", "auto") not in ("", "auto"):
        forced = os.environ["BOT_LANGUAGE"]
    if forced:
        if forced not in LANGUAGES:
            sys.exit(f"❌ Unknown language '{forced}' — use one of {', '.join(LANGUAGES)}")
        return forced

    available = [l for l in LANGUAGES if pending_count(l) > 0]
    if not available:
        return "en"   # get_quote() reports that every list is used up
    lang = min(available, key=last_posted_at)
    print(f"🌐 Language: {LANGUAGES[lang]['name']}  (posted least recently)")
    return lang


def get_quote(lang):
    # BOT_QUOTE_ID (workflow "quote_id" input) posts one specific entry instead of the next one
    chosen = os.environ.get("BOT_QUOTE_ID", "").strip()
    try:
        quote = get_quote_by_id(int(chosen), lang) if chosen else get_next_quote(lang)
    except RuntimeError as e:
        # Never recycle old quotes — repeated uploads get the channel
        # flagged as repetitive content. Fail loudly so new quotes get added.
        print(e)
        sys.exit(1)
    print(f"📋 Quote source: {os.path.basename(quotes_file(lang))} (id={quote['id']})")
    return quote


# ─────────────────────────────────────────────
# 1b️⃣  Hook line — names the author so viewers know who it's about
# ─────────────────────────────────────────────
def get_hook(author, lang="en"):
    return random.choice(LANG_CONFIG[lang]["hooks"]).format(a=author or "")


# ─────────────────────────────────────────────
# 2️⃣  Split quote into segments
# ─────────────────────────────────────────────
def split_into_segments(quote_text, min_words=3, uppercase=True):
    import re
    raw      = re.split(r'[.,!?]+', quote_text)
    segments = [s.strip() for s in raw if s.strip()]
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
    case = str.upper if uppercase else str
    segments = [case(s) for s in merged if s]
    return segments if segments else [case(quote_text)]


# ─────────────────────────────────────────────
# 3️⃣  Caption frame — large, few words at a time, current word highlighted
# ─────────────────────────────────────────────
CAPTION_MAX_WORDS = 3
CAPTION_MAX_CHARS = 16


def _chunk_words(words, max_words=CAPTION_MAX_WORDS, max_chars=CAPTION_MAX_CHARS):
    """Group words into short caption chunks (≤3 words / ≤16 chars)."""
    chunks, cur = [], []
    for w in words:
        if cur and (len(cur) >= max_words or len(" ".join(cur + [w])) > max_chars):
            chunks.append(cur)
            cur = []
        cur.append(w)
    if cur:
        chunks.append(cur)
    return chunks


def _wrap_words(words, font, max_w):
    """Greedy pixel-width wrap. Returns a list of lines (each a list of words)."""
    lines, cur = [], []
    for w in words:
        if cur and font.getlength(" ".join(cur + [w])) > max_w:
            lines.append(cur)
            cur = []
        cur.append(w)
    if cur:
        lines.append(cur)
    return lines


def render_caption_image(words, highlight_idx, frame_id, size=(1080, 1920),
                         font_path=BOLD_FONT, line_spacing=1.22):
    W, H = size
    # Keep clear of the Shorts like/comment buttons on the right edge
    max_w = W * 0.78

    font, lines = None, None
    for fs in range(int(W * 0.09), int(W * 0.05) - 1, -4):   # ~96px → ~54px at 1080 wide
        font  = ImageFont.truetype(font_path, fs)
        lines = _wrap_words(words, font, max_w)
        if len(lines) <= 2 and all(font.getlength(" ".join(l)) <= max_w for l in lines):
            break

    img    = Image.new("RGBA", size, (0, 0, 0, 0))
    draw   = ImageDraw.Draw(img)
    stroke = max(4, font.size // 11)
    line_h = int(font.size * line_spacing)
    y      = int(H * 0.52) - (line_h * len(lines)) // 2
    space  = font.getlength(" ")

    wi = 0
    for line in lines:
        x = (W - font.getlength(" ".join(line))) / 2
        for word in line:
            color = (255, 222, 0) if wi == highlight_idx else (255, 255, 255)
            draw.text((x + 4, y + 6), word, font=font, fill=(0, 0, 0, 150))   # drop shadow
            draw.text((x, y), word, font=font, fill=color,
                      stroke_width=stroke, stroke_fill=(0, 0, 0))
            x  += font.getlength(word) + space
            wi += 1
        y += line_h

    path = f"/tmp/caption_{frame_id:04d}.png"
    img.save(path)
    return path


# ─────────────────────────────────────────────
# 3b️⃣  Caption clips
# ─────────────────────────────────────────────
def build_quote_slides(segments, start_times, durations, size, lang="en"):
    cfg      = LANG_CONFIG[lang]
    slides   = []
    frame_id = 0
    for seg_i, (seg, seg_start, seg_dur) in enumerate(zip(segments, start_times, durations)):
        words = (seg.upper() if cfg["uppercase"] else seg).split()
        if not words:
            continue
        char_counts = [max(len(w), 1) for w in words]
        total_chars = sum(char_counts)
        preview = seg[:50] + ("..." if len(seg) > 50 else "")
        print(f"   📝 Segment {seg_i+1}: [{seg_start:.2f}s → {seg_start+seg_dur:.2f}s]  \"{preview}\"  ({len(words)} words)")
        word_start = seg_start
        for chunk in _chunk_words(words, max_chars=cfg["caption_chars"]):
            for w_i, word in enumerate(chunk):
                wdur = seg_dur * (max(len(word), 1) / total_chars)
                img_path = render_caption_image(chunk, w_i, frame_id, size=size,
                                                font_path=cfg["caption_font"],
                                                line_spacing=cfg["line_spacing"])
                slides.append(ImageClip(img_path).set_start(word_start).set_duration(wdur))
                word_start += wdur
                frame_id   += 1
    return slides


# ─────────────────────────────────────────────
# 4️⃣  Author name overlay (top of frame, clear of the Shorts UI)
# ─────────────────────────────────────────────
def create_author_image(author, size=(1080, 1920), font_path=ITALIC_FONT, uppercase=True, prefix="— "):
    W, H = size
    img  = Image.new("RGBA", size, (0, 0, 0, 0))
    text = f"{prefix}{author.upper() if uppercase else author}"
    font = None
    tw = th = 0
    for fs in range(int(W * 0.056), 26, -2):   # ~60px at 1080 wide
        font = ImageFont.truetype(font_path, fs)
        bbox = ImageDraw.Draw(img).textbbox((0, 0), text, font=font)
        tw, th = bbox[2] - bbox[0], bbox[3]
        if tw <= W * 0.80:
            break
    tx, ty = (W - tw) // 2, int(H * 0.17)
    pad_x, pad_y = 30, 18
    ov = Image.new("RGBA", size, (0, 0, 0, 0))
    ImageDraw.Draw(ov).rounded_rectangle(
        [tx - pad_x, ty - pad_y, tx + tw + pad_x, ty + th + pad_y + 8],
        radius=20, fill=(0, 0, 0, 170))
    img  = Image.alpha_composite(img, ov)
    ImageDraw.Draw(img).text((tx, ty), text, font=font, fill=(255, 215, 60),
                             stroke_width=2, stroke_fill=(0, 0, 0))
    path = "/tmp/author_overlay.png"
    img.save(path)
    return path


# ─────────────────────────────────────────────
# 5️⃣  Pexels video URLs
# ─────────────────────────────────────────────
def get_video_urls(keyword="nature", count=5):
    key = os.environ.get("PEXELS_API_KEY")
    if not key:
        print("❌ Missing PEXELS_API_KEY")
        return []
    urls = []
    try:
        r = requests.get(
            "https://api.pexels.com/videos/search",
            headers={"Authorization": key},
            params={"query": keyword, "per_page": min(count * 2, 20),
                    "orientation": "portrait", "size": "large"},
            timeout=10,
        )
        if r.status_code != 200:
            return []
        videos = r.json().get("videos", [])
        random.shuffle(videos)
        for video in videos:
            files = video.get("video_files", [])
            def hd_score(vf):
                w, h   = vf.get("width", 0), vf.get("height", 0)
                is_mp4 = vf.get("file_type") == "video/mp4"
                is_hd  = h >= 1920 or w >= 1080
                return (0 if is_mp4 else 1, 0 if is_hd else 1, -(h or 0))
            for vf in sorted(files, key=hd_score):
                if vf.get("file_type") == "video/mp4":
                    w, h = vf.get("width", 0), vf.get("height", 0)
                    urls.append(vf["link"])
                    print(f"   📹 Pexels clip {len(urls)}: {w}×{h}")
                    break
            if len(urls) >= count:
                break
    except Exception as e:
        print(f"⚠️ Pexels error: {e}")
    return urls


# ─────────────────────────────────────────────
# 5b  NASA Image & Video Library — real galaxy/space footage
#     (NASA media is generally not copyrighted; no API key needed)
# ─────────────────────────────────────────────
NASA_API = "https://images-api.nasa.gov"
# Skip talking heads, press events and launches — we want space visuals
NASA_SKIP_WORDS = ("briefing", "conference", "interview", "launch", "rollout", "panel",
                   "event", "news", "update", "live", "q&a", "podcast", "b-roll of",
                   "ceremony", "remarks", "hangout", "chat")


def get_nasa_video_urls(query, count=3):
    """Return mp4 URLs of NASA videos matching the query (medium/small renditions)."""
    urls = []
    try:
        r = requests.get(f"{NASA_API}/search",
                         params={"q": query, "media_type": "video", "page_size": 40},
                         timeout=15)
        if r.status_code != 200:
            print(f"   ⚠️  NASA search '{query}' → HTTP {r.status_code}")
            return []
        items = r.json().get("collection", {}).get("items", [])
        random.shuffle(items)
        for item in items:
            meta  = (item.get("data") or [{}])[0]
            title = meta.get("title", "")
            if any(w in title.lower() for w in NASA_SKIP_WORDS):
                continue
            files = requests.get(item["href"], timeout=15).json()   # list of file URLs
            mp4s  = [f for f in files if isinstance(f, str) and f.endswith(".mp4")]
            pick  = (next((f for f in mp4s if "~medium" in f), None)
                     or next((f for f in mp4s if "~small" in f), None)
                     or next((f for f in mp4s if "~mobile" in f), None))
            if not pick:
                continue
            urls.append(pick.replace("http://", "https://", 1))
            print(f"   🔭 NASA clip {len(urls)}: {title[:60]}")
            if len(urls) >= count:
                break
    except Exception as e:
        print(f"⚠️ NASA error: {e}")
    return urls


# ─────────────────────────────────────────────
# 6️⃣  Download video
# ─────────────────────────────────────────────
def download_video(url):
    print("⬇️ Downloading video...")
    resp = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, stream=True, timeout=30)
    if resp.status_code != 200:
        raise Exception("Failed to download video")
    if int(resp.headers.get("Content-Length") or 0) > 150 * 1024 * 1024:
        raise Exception("Video too large (>150 MB) — skipping")
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".mp4")
    for chunk in resp.iter_content(chunk_size=1024 * 1024):
        if chunk:
            tmp.write(chunk)
    tmp.close()
    print("✅ Video downloaded:", tmp.name)
    return tmp.name


# ─────────────────────────────────────────────
# Portrait conversion
# ─────────────────────────────────────────────
SHORTS_W, SHORTS_H = 1080, 1920

def _to_portrait(clip):
    cw, ch = clip.w, clip.h
    if cw == SHORTS_W and ch == SHORTS_H:
        return clip
    if cw > ch:
        scale = SHORTS_H / ch
        new_w = int(cw * scale)
        clip  = clip.resize((new_w, SHORTS_H))
        x_off = (new_w - SHORTS_W) // 2
        clip  = clip.crop(x1=x_off, y1=0, x2=x_off + SHORTS_W, y2=SHORTS_H)
    else:
        scale = max(SHORTS_W / cw, SHORTS_H / ch)
        new_w = int(cw * scale)
        new_h = int(ch * scale)
        clip  = clip.resize((new_w, new_h))
        x_off = (new_w - SHORTS_W) // 2
        y_off = (new_h - SHORTS_H) // 2
        clip  = clip.crop(x1=x_off, y1=y_off, x2=x_off + SHORTS_W, y2=y_off + SHORTS_H)
    return clip


# ─────────────────────────────────────────────
# 6b️⃣  Build background clip from the author's sport
# ─────────────────────────────────────────────
def build_background(keywords, target, nasa_keywords=()):
    """
    keywords      : Pexels searches, tried in order (the whole list is the fallback —
                    a space Short never falls back to sports footage)
    nasa_keywords : NASA video library searches, tried first (real galaxy footage)
    """
    SEG_DUR  = 2.5   # fast cuts hold attention better than long static shots
    keywords      = list(dict.fromkeys(keywords))        # de-duplicate, keep order
    nasa_keywords = list(dict.fromkeys(nasa_keywords))

    nasa_urls = []
    for kw in nasa_keywords:
        print(f"   🔭 NASA keyword: '{kw}'")
        nasa_urls += [u for u in get_nasa_video_urls(kw, count=2) if u not in nasa_urls]
        if len(nasa_urls) >= 4:
            break

    urls = []
    for kw in keywords:
        if len(nasa_urls) + len(urls) >= 6:
            break
        print(f"   🎨 Footage keyword: '{kw}'")
        urls += [u for u in get_video_urls(kw, count=4) if u not in urls]
    random.shuffle(nasa_urls)
    random.shuffle(urls)
    urls = nasa_urls + urls   # NASA footage first when we have it
    nasa = set(nasa_urls)

    segs, total = [], 0.0
    for url in urls:
        if total >= target:
            break
        try:
            raw = VideoFileClip(download_video(url))
            if url in nasa and raw.duration > 20:
                # NASA videos often open on title cards/logos — cut from the middle
                start = random.uniform(raw.duration * 0.25, raw.duration * 0.65)
            else:
                # Skip the first second — stock clips often open on a static frame
                start = 1.0 if raw.duration > SEG_DUR + 1.5 else 0.0
            seg   = _to_portrait(raw.subclip(start, min(raw.duration, start + SEG_DUR)))
            segs.append(seg)
            total += seg.duration
            print(f"   ✂️  clip {len(segs)}: {seg.duration:.1f}s  (total {total:.1f}s)")
        except Exception as e:
            print(f"   ⚠️  Clip failed: {e}")

    if not segs:
        raise RuntimeError("No video clips could be loaded.")

    # Not enough footage — cycle through what we have
    i = 0
    while total < target:
        seg = segs[i % len(segs)]
        segs.append(seg)
        total += seg.duration
        i += 1

    combined = concatenate_videoclips(segs, method="compose").subclip(0, target)
    print(f"✅ Combined clip: {combined.duration:.2f}s  @ {SHORTS_W}×{SHORTS_H}")
    return combined


# ─────────────────────────────────────────────
# 7️⃣  TTS
# ─────────────────────────────────────────────
import asyncio

EDGE_RATE   = "-4%"
EDGE_VOLUME = "+0%"


def _clean_text(text):
    import re
    t = text.replace("—", " ").replace("–", " ").replace("…", " ")
    t = t.replace("“", "").replace("”", "").replace("’", "'")
    # Keep Malayalam letters (U+0D00–U+0D7F) and the zero-width joiners it relies on
    t = re.sub(r"[^a-zA-Z0-9\u0D00-\u0D7F\u200C\u200D \',\.!\?]", " ", t)
    t = re.sub(r"[\',\.!\?]{2,}", ".", t)
    t = re.sub(r" {2,}", " ", t).strip()
    t = re.sub(r"[\',\.!\? ]+$", "", t) + "."
    return t


def _trim_silence(input_path, output_path, silence_thresh=-45):
    cmd = ["ffmpeg", "-y", "-i", input_path, "-af",
           f"silenceremove=stop_periods=-1:stop_duration=0.3:stop_threshold={silence_thresh}dB",
           output_path]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        import shutil
        shutil.copy(input_path, output_path)


async def _edge_tts_async(text, mp3_path, voice):
    import edge_tts
    communicate = edge_tts.Communicate(text, voice, rate=EDGE_RATE, volume=EDGE_VOLUME)
    await communicate.save(mp3_path)


def _synth_edge(text, path, voice):
    clean     = _clean_text(text)
    mp3_path  = path.replace(".wav", "_edge.mp3")
    trim_path = path.replace(".wav", "_trim.wav")
    asyncio.run(_edge_tts_async(clean, mp3_path, voice))
    subprocess.run(["ffmpeg", "-y", "-i", mp3_path, "-ar", "22050", path], capture_output=True)
    _trim_silence(path, trim_path)
    import shutil
    shutil.move(trim_path, path)
    return len(AudioSegment.from_file(path)) / 1000.0


def _synth_coqui(text, path, tts_engine, speaker):
    import shutil
    clean     = _clean_text(text)
    raw_path  = path.replace(".wav", "_raw.wav")
    trim_path = path.replace(".wav", "_trim.wav")
    kw = {"text": clean, "file_path": raw_path}
    if speaker:
        kw["speaker"] = speaker
    tts_engine.tts_to_file(**kw)
    _trim_silence(raw_path, trim_path)
    result = subprocess.run(
        ["ffmpeg", "-y", "-i", trim_path, "-filter:a", "atempo=0.95", "-ar", "22050", path],
        capture_output=True, text=True)
    if result.returncode != 0:
        shutil.copy(trim_path, path)
    return len(AudioSegment.from_file(path)) / 1000.0


def _pick_voice(gender, lang="en"):
    voice = random.choice(LANG_CONFIG[lang]["voices"][gender])
    print(f"🎙  Voice: {voice}  ({gender})")
    return voice


def _synth_one(text, path, voice, coqui_cfg):
    try:
        dur = _synth_edge(text, path, voice)
        print(f"      via edge-tts  ({dur:.2f}s)")
        return dur
    except Exception as e:
        print(f"   ⚠️  edge-tts failed: {e}")
        if coqui_cfg is None:
            raise RuntimeError(f"edge-tts failed and there is no offline fallback for this language: {e}")
    try:
        tts = TTS(model_name=coqui_cfg["model"], progress_bar=False, gpu=False)
        dur = _synth_coqui(text, path, tts, coqui_cfg["speaker_idx"])
        print(f"      via Coqui offline  ({dur:.2f}s)")
        return dur
    except Exception as e:
        raise RuntimeError(f"All TTS engines failed: {e}")


def generate_audio_segments(segments, gender, lang="en"):
    PAUSE_MS    = 150
    voice       = _pick_voice(gender, lang)
    # The offline Coqui models are English-only
    coqui_cfg   = VOICE_COQUI[gender] if lang == "en" else None
    paths, durs = [], []
    for i, seg in enumerate(segments):
        path = f"/tmp/tts_seg_{i:02d}.wav"
        dur  = _synth_one(seg, path, voice, coqui_cfg)
        paths.append(path)
        durs.append(dur)
        print(f"   🔊 Segment {i+1}: {dur:.2f}s  \"{seg[:50]}\"")
    return paths, durs, PAUSE_MS


# ─────────────────────────────────────────────
# 8️⃣  Assemble audio
# ─────────────────────────────────────────────
def assemble_audio(tts_paths, durations, pause_ms, music_file):
    PAUSE    = AudioSegment.silent(duration=pause_ms)
    voice    = AudioSegment.empty()
    for path in tts_paths:
        voice += AudioSegment.from_file(path).apply_gain(5) + PAUSE
    total_ms = len(voice)
    total_s  = total_ms / 1000.0
    bg = AudioSegment.from_file(music_file).apply_gain(-18)
    if len(bg) < total_ms:
        bg = bg * (total_ms // len(bg) + 1)
    bg    = bg[:total_ms]
    mixed = voice.overlay(bg)
    out   = "/tmp/final_audio.wav"
    mixed.export(out, format="wav")
    print(f"✅ Audio assembled: {total_s:.2f}s")
    return AudioFileClip(out).set_duration(total_s), total_s


# ─────────────────────────────────────────────
# 9️⃣  Build YouTube Short
# ─────────────────────────────────────────────
def create_youtube_short(quote, lang="en"):
    cfg        = LANG_CONFIG[lang]
    quote_text = quote["text"]
    if cfg["kind"] == "fact":
        items    = quote.get("items", [quote])
        topic    = FACT_TOPICS.get(quote.get("topic"), FACT_TOPICS["earth"])
        sport    = None
        gender   = random.choice(["male", "female"])
        own      = [f["footage"] for f in items]
        keywords = own + random.sample(topic["keywords"], len(topic["keywords"]))
        nasa_kws = own + topic.get("nasa", []) if topic.get("nasa") else []
        overlay  = dict(author=topic["label"], prefix="")
        hook     = fact_list_hook(topic, len(items)) if len(items) > 1 else get_hook(None, lang)
    else:
        # Name as spoken/shown in this language; footage + voice use the English name
        shown_name = quote.get(f"author_{lang}", quote["author"])
        sport, gender = author_profile(quote["author"])
        keywords = random.sample(SPORT_KEYWORDS.get(sport, DEFAULT_SPORT_KEYWORDS),
                                 len(SPORT_KEYWORDS.get(sport, DEFAULT_SPORT_KEYWORDS)))
        keywords += DEFAULT_SPORT_KEYWORDS
        nasa_kws = []
        overlay  = dict(author=shown_name)
        hook     = get_hook(shown_name, lang)
    if cfg["kind"] == "fact" and len(items) > 1:
        body = []
        for i, f in enumerate(items, 1):
            body += [f"{ML_NUMBERS[i]}."] + split_into_segments(f["text"], uppercase=False)
    else:
        body = split_into_segments(quote_text, uppercase=cfg["uppercase"])
    segments = [hook] + body + [cfg["ending"]]
    print(f"📝 {len(segments)} segment(s) detected (incl. hook + loop ending)")

    tts_paths, durations, pause_ms = generate_audio_segments(segments, gender, lang)
    pause_s = pause_ms / 1000.0

    seg_starts, seg_durs = [], []
    cursor = 0.0
    for d in durations:
        seg_starts.append(cursor)
        seg_durs.append(d + pause_s)
        cursor += d + pause_s
    total_dur = cursor

    print(f"⏱  Total duration: {total_dur:.2f}s")

    clip = build_background(keywords, target=total_dur, nasa_keywords=nasa_kws)
    W, H = clip.w, clip.h

    slide_clips = build_quote_slides(segments, seg_starts, seg_durs, size=(W, H), lang=lang)

    # Author name (or fact topic) stays on screen for the whole quote/fact
    author_start = seg_starts[1]
    author_clip = (
        ImageClip(create_author_image(size=(W, H), font_path=cfg["author_font"],
                                      uppercase=cfg["uppercase"], **overlay))
        .set_start(author_start)
        .set_duration(seg_starts[-1] - author_start)
        .crossfadein(0.3)
    )

    music_file    = random.choice(["music1.mp3", "music2.mp3", "music3.mp3"])
    audio_clip, _ = assemble_audio(tts_paths, durations, pause_ms, music_file)

    # No intro card: the video opens straight on moving footage + the spoken hook,
    # which is what stops viewers swiping away in the first second.
    final = CompositeVideoClip([clip] + slide_clips + [author_clip]).set_audio(audio_clip)

    out = "/tmp/youtube_short.mp4"
    print("🎞 Rendering video...")
    final.write_videofile(out, fps=30, codec="libx264", audio_codec="aac", threads=2)
    print(f"✅ Video saved: {out}")
    return out, sport


# ─────────────────────────────────────────────
# 🔟  Title / description / tags
# ─────────────────────────────────────────────
def build_metadata(quote, sport, lang="en"):
    """Searchable metadata: the author and quote in the title, full quote in the description."""
    cfg        = LANG_CONFIG[lang]
    quote_text = quote["text"]
    if cfg["kind"] == "fact":
        return _fact_metadata(quote, cfg)
    author     = quote["author"]
    shown_name = quote.get(f"author_{lang}")
    suffix     = f" – {author} #shorts" + (" #malayalam" if cfg["yt_language"] == "ml" else "")
    budget = 100 - len(suffix) - 2   # YouTube title limit is 100 chars; 2 for the quote marks
    quote  = quote_text.strip()
    if len(quote) > budget:
        quote = quote[:budget - 1].rsplit(" ", 1)[0].rstrip(",.;:!?") + "…"
    title = f"\"{quote}\"{suffix}".replace("<", "").replace(">", "")

    author_tag  = "#" + "".join(ch for ch in author if ch.isalnum())
    sport_tag   = f" #{sport.replace(' ', '')}" if sport else ""
    byline      = f"{shown_name} ({author})" if shown_name else author
    description = (
        f"\"{quote_text}\"\n— {byline}\n\n"
        f"{author_tag}{sport_tag} {cfg['hashtags']}"
    )
    tags = cfg["tags"] + [author, f"{author} quotes"]
    if shown_name:
        tags.append(shown_name)
    if sport:
        tags += [sport, f"{sport} motivation"]
    return title, description, tags


def _fact_metadata(fact, cfg):
    """Fact Shorts: the fact (or "N things about <topic>") as the title, all facts in the description."""
    items  = fact.get("items", [fact])
    suffix = " #shorts #malayalam #facts"
    budget = 100 - len(suffix)
    if len(items) > 1:
        topic = FACT_TOPICS.get(fact.get("topic"), FACT_TOPICS["earth"])
        text  = f"{topic['about']} അധികമാർക്കും അറിയാത്ത {len(items)} കാര്യങ്ങൾ"
    else:
        text  = fact["text"].strip()
    if len(text) > budget:
        text = text[:budget - 1].rsplit(" ", 1)[0].rstrip(",.;:!?") + "…"
    title  = f"{text}{suffix}".replace("<", "").replace(">", "")
    topic_tag = {"space": " #space #galaxy #universe", "aliens": " #aliens #space #universe",
                 "animals": " #animals #nature", "body": " #humanbody",
                 "earth": " #earth #nature"}.get(fact.get("topic"), "")
    if len(items) > 1:
        body = "\n\n".join(f"{i}. {f['text']}" for i, f in enumerate(items, 1))
    else:
        body = fact["text"]
    description = f"{body}\n\n{cfg['hashtags']}{topic_tag}"
    tags = cfg["tags"] + [fact.get("topic", "")] + [f.get("footage", "") for f in items]
    return title, description, list(dict.fromkeys(t for t in tags if t))


# ─────────────────────────────────────────────
# 1️⃣1️⃣  Upload to YouTube
# ─────────────────────────────────────────────
def upload_to_youtube(video_path, quote, sport, lang="en"):
    from google.oauth2.credentials import Credentials
    from googleapiclient.discovery import build
    from googleapiclient.http import MediaFileUpload
    import google.auth.transport.requests

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

    title, description, tags = build_metadata(quote, sport, lang)
    print(f"🏷  Title: {title}")
    body = {
        "snippet": {
            "title":       title,
            "description": description,
            "tags":        tags,
            "categoryId":  LANG_CONFIG[lang]["category"],
            # Tells YouTube which viewers to recommend it to — essential on a
            # channel that mixes English and Malayalam videos
            "defaultLanguage":      LANG_CONFIG[lang]["yt_language"],
            "defaultAudioLanguage": LANG_CONFIG[lang]["yt_language"],
        },
        "status": {"privacyStatus": "public", "selfDeclaredMadeForKids": False},
    }
    resp = (
        youtube.videos()
        .insert(part="snippet,status", body=body,
                media_body=MediaFileUpload(video_path, chunksize=-1, resumable=True))
        .execute()
    )
    video_id = resp["id"]
    print(f"✅ Uploaded! https://youtube.com/shorts/{video_id}")
    return video_id


# ─────────────────────────────────────────────
# 1️⃣2️⃣  Git commit — MUST be defined BEFORE main()
# ─────────────────────────────────────────────
def _git_commit_status(quote_id, lang: str = "en") -> bool:
    """
    Commit and push the updated quote file back to GitHub.
    Called after mark_posted() so the status change survives the
    ephemeral GitHub Actions runner and is available on the next run.
    Safe locally: skips silently if not inside a git repo.
    Returns False if the change could not be pushed.
    """
    def _run(cmd):
        return subprocess.run(
            cmd, capture_output=True, text=True,
            cwd=os.path.dirname(os.path.abspath(__file__))
        )

    if _run(["git", "rev-parse", "--is-inside-work-tree"]).returncode != 0:
        print("ℹ️  Not a git repo — skipping status commit.")
        return True

    _run(["git", "config", "user.name",  "github-actions[bot]"])
    _run(["git", "config", "user.email", "github-actions[bot]@users.noreply.github.com"])

    filename = os.path.basename(quotes_file(lang))
    stage = _run(["git", "add", filename])
    if stage.returncode != 0:
        print(f"⚠️  git add failed: {stage.stderr.strip()}")
        return False

    if _run(["git", "diff", "--staged", "--quiet"]).returncode == 0:
        print(f"ℹ️  {filename} unchanged — nothing to commit.")
        return True

    label  = {"en": "quote", "ml": "Malayalam quote", "ml_facts": "Malayalam fact"}.get(lang, lang)
    if isinstance(quote_id, (list, tuple)):
        label, quote_id = label + "s", ",".join(str(i) for i in quote_id)
    msg    = f"chore: mark {label} id={quote_id} as posted [skip ci]"
    commit = _run(["git", "commit", "-m", msg])
    if commit.returncode != 0:
        print(f"⚠️  git commit failed: {commit.stderr.strip()}")
        return False
    print(f"📝 Git commit: {msg}")

    # Pick up anything pushed while the video was rendering
    _run(["git", "pull", "--rebase"])
    push = _run(["git", "push"])
    if push.returncode != 0:
        print(f"⚠️  git push failed: {push.stderr.strip()}")
        print("   Ensure the workflow has  permissions: contents: write")
        return False
    print(f"🚀 {filename} pushed to repo — status persisted for next run.")
    return True


# ─────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────
def main():
    if "--status" in sys.argv:
        for lang in LANGUAGES:
            show_status(lang)
        return

    if "--reset" in sys.argv:
        reset_all(pick_language())
        return

    lang  = pick_language()
    quote = get_quote(lang)
    if LANG_CONFIG[lang]["kind"] == "fact":
        quote["items"] = fact_items(quote, lang)
        print(f"🧩 Facts in this Short: {[f['id'] for f in quote['items']]}")
    print(f"\n💡 Quote : {quote['text']}")
    print(f"✍️  Author/topic: {quote.get('author') or quote.get('topic')}")
    print(f"🔖 Quote ID: {quote['id']}  ({LANGUAGES[lang]['name']})")

    video_path, sport = create_youtube_short(quote, lang)
    upload_to_youtube(video_path, quote, sport, lang)

    ids = [q["id"] for q in quote.get("items", [quote])]
    for qid in ids:
        mark_posted(qid, lang)
    if not _git_commit_status(ids if len(ids) > 1 else ids[0], lang):
        # The video is live but the status wasn't saved — fail the job so it's
        # noticed before the next run re-posts the same quote.
        print(f"\n❌ Quote id={quote['id']} was uploaded but its status could not be pushed.")
        sys.exit(1)
    print(f"\n📊 Quote files updated — run  python youtube_bot.py --status  to see all quotes.")


if __name__ == "__main__":
    main()
