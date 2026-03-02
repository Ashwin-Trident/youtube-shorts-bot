import requests, random, os
from moviepy.editor import VideoFileClip, TextClip, CompositeVideoClip

# YouTube Shorts resolution
WIDTH, HEIGHT = 720, 1280

# Pexels API key (get free from https://www.pexels.com/api/)
PEXELS_API_KEY = "PEXELS_API_KEY"

# Themes for quotes
THEMES = ["nature", "city", "mountain", "beach", "forest", "space"]

def get_quote():
    r = requests.get("https://api.quotable.io/random")
    if r.status_code == 200:
        data = r.json()
        return data["content"]
    return "Dream big and shine!"

def get_stock_video(query):
    headers = {"Authorization": PEXELS_API_KEY}
    r = requests.get(f"https://api.pexels.com/videos/search?query={query}&orientation=portrait&size=medium&per_page=10", headers=headers)
    data = r.json()
    if data["videos"]:
        video_url = random.choice(data["videos"])["video_files"][0]["link"]
        filename = f"{query}.mp4"
        with open(filename, "wb") as f:
            f.write(requests.get(video_url).content)
        return filename
    return None

def create_youtube_short():
    quote = get_quote()
    theme = random.choice(THEMES)
    print(f"💡 Quote: {quote}")
    print(f"🎬 Theme video: {theme}")

    video_file = get_stock_video(theme)
    if not video_file:
        print("❌ Could not fetch video")
        return

    clip = VideoFileClip(video_file).resize(height=HEIGHT).crop(x1=0, y1=0, width=WIDTH, height=HEIGHT)
    
    txt_clip = TextClip(quote, fontsize=60, color="white", method="caption", size=(WIDTH-60, None), align="center")
    txt_clip = txt_clip.set_position(("center", HEIGHT//2 - 100)).set_duration(clip.duration)

    final_clip = CompositeVideoClip([clip, txt_clip])
    final_clip.write_videofile("youtube_short.mp4", fps=24)
    print("✅ Video saved as youtube_short.mp4")

if __name__ == "__main__":
    create_youtube_short()
