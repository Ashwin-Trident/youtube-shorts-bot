import os
import requests
from moviepy.editor import VideoFileClip, TextClip, CompositeVideoClip

# -----------------------------
# CONFIG
# -----------------------------
PEXELS_API_KEY = os.getenv("PEXELS_API_KEY")  # set this in GitHub secrets
OUTPUT_FILE = "short.mp4"
VIDEO_DURATION = 15  # seconds

# -----------------------------
# Step 1: Get a random quote (free API)
# -----------------------------
def get_quote():
    try:
        r = requests.get("https://api.quotable.io/random", timeout=10)
        data = r.json()
        return f"{data['content']} — {data['author']}"
    except Exception as e:
        print("⚠️ Failed to get quote, using default.")
        return "Believe in yourself — Unknown"

# -----------------------------
# Step 2: Search for free stock video on Pexels
# -----------------------------
def get_video_url(keyword="nature"):
    headers = {"Authorization": PEXELS_API_KEY}
    params = {"query": keyword, "orientation": "portrait", "size": "medium", "per_page": 1}
    try:
        r = requests.get("https://api.pexels.com/videos/search", headers=headers, params=params, timeout=10)
        data = r.json()
        if data["videos"]:
            return data["videos"][0]["video_files"][0]["link"]
        else:
            print("⚠️ No video found, using default video")
            return "https://player.vimeo.com/external/5184436.hd.mp4?s=example"  # fallback
    except Exception as e:
        print("⚠️ Pexels API error:", e)
        return None

# -----------------------------
# Step 3: Download video locally
# -----------------------------
def download_video(url, filename="video.mp4"):
    r = requests.get(url, stream=True)
    with open(filename, "wb") as f:
        for chunk in r.iter_content(chunk_size=8192):
            f.write(chunk)
    return filename

# -----------------------------
# Step 4: Create video with quote overlay
# -----------------------------
def create_youtube_short(quote, video_file):
    clip = VideoFileClip(video_file).subclip(0, VIDEO_DURATION)

    txt_clip = TextClip(
        quote,
        fontsize=60,
        color="white",
        font="DejaVu-Sans",  # Must be installed on GitHub Actions
        method="caption",
        size=(clip.w - 100, None),
        align="center"
    ).set_position("center").set_duration(clip.duration)

    final_clip = CompositeVideoClip([clip, txt_clip])
    final_clip.write_videofile(OUTPUT_FILE, fps=24)
    print(f"✅ Video saved as {OUTPUT_FILE}")

# -----------------------------
# Main
# -----------------------------
def main():
    quote = get_quote()
    print("💡 Selected quote:", quote)

    # Use a keyword from the quote to find related video
    keyword = quote.split()[0]  # first word
    print(f"🎬 Searching video for keyword: {keyword}")
    video_url = get_video_url(keyword)
    if not video_url:
        print("❌ Could not find video. Exiting.")
        return

    video_file = download_video(video_url)
    create_youtube_short(quote, video_file)

if __name__ == "__main__":
    main()
