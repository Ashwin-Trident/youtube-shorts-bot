import json
import random
import requests
from moviepy.editor import VideoFileClip, TextClip, CompositeVideoClip
import os

# -------------------------
# Config
# -------------------------
PEXELS_API_KEY = os.environ.get("PEXELS_API_KEY")  # set in GitHub secrets
QUOTE_FILE = "quotes.json"
OUTPUT_FILE = "short.mp4"

# -------------------------
# Functions
# -------------------------
def get_quote():
    with open(QUOTE_FILE, "r") as f:
        quotes = json.load(f)
    return random.choice(quotes)

def get_video(keyword="nature"):
    headers = {"Authorization": PEXELS_API_KEY}
    url = f"https://api.pexels.com/videos/search?query={keyword}&per_page=1"
    r = requests.get(url, headers=headers).json()
    if "videos" in r and r["videos"]:
        return r["videos"][0]["video_files"][0]["link"]
    else:
        # fallback video if API returns nothing
        return "https://player.vimeo.com/external/449387312.sd.mp4?s=xxx"  # Replace with free video URL

def create_youtube_short():
    # 1. Get quote
    quote = get_quote()
    print(f"💡 Selected quote: {quote}")

    # 2. Pick a keyword from the quote
    keyword = random.choice([w for w in quote.split() if len(w) > 3])
    print(f"🎬 Searching video for keyword: {keyword}")

    # 3. Get video URL
    video_url = get_video(keyword)
    print(f"🎥 Video URL: {video_url}")

    # 4. Create MoviePy clip
    clip = VideoFileClip(video_url).subclip(0, 15)  # 15-second short
    txt_clip = TextClip(quote, fontsize=50, color="white", method="caption", size=clip.size)
    txt_clip = txt_clip.set_position("center").set_duration(clip.duration)

    final = CompositeVideoClip([clip, txt_clip])
    final.write_videofile(OUTPUT_FILE, fps=24)
    print(f"✅ Short saved as {OUTPUT_FILE}")

# -------------------------
# Main
# -------------------------
if __name__ == "__main__":
    create_youtube_short()
