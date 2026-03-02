# youtube_bot.py
import requests
from moviepy.editor import VideoFileClip, ImageClip, CompositeVideoClip
from PIL import Image, ImageDraw, ImageFont
import random
import os

# 1️⃣ Free quote API
def get_quote():
    try:
        r = requests.get("https://api.quotable.io/random", timeout=10)
        if r.status_code == 200:
            data = r.json()
            return f"{data['content']} — {data['author']}"
    except Exception as e:
        print("⚠️ Failed to get quote, using default.")
    # default quote
    default_quotes = [
        "Believe in yourself — Unknown",
        "Success comes from persistence — Unknown",
        "Every day is a new opportunity — Unknown",
    ]
    return random.choice(default_quotes)

# 2️⃣ Create text image using Pillow
def create_text_image(text, size=(1080, 1920), font_path=None, font_size=80):
    img = Image.new("RGBA", size, (0, 0, 0, 0))  # transparent background
    draw = ImageDraw.Draw(img)

    # Default font
    if font_path:
        font = ImageFont.truetype(font_path, font_size)
    else:
        font = ImageFont.load_default()

    # Get text bounding box
    bbox = draw.textbbox((0, 0), text, font=font)
    text_width = bbox[2] - bbox[0]
    text_height = bbox[3] - bbox[1]

    x = (size[0] - text_width) // 2
    y = (size[1] - text_height) // 2

    draw.text((x, y), text, font=font, fill="white")
    
    path = "/tmp/text_overlay.png"
    img.save(path)
    return path

# 3️⃣ Search free Pexels videos
def get_video_url(keyword="nature"):
    PEXELS_API_KEY = os.environ.get("PEXELS_API_KEY")
    headers = {"Authorization": PEXELS_API_KEY}
    params = {"query": keyword, "per_page": 10, "orientation": "portrait", "size": "medium"}
    r = requests.get("https://api.pexels.com/videos/search", headers=headers, params=params, timeout=10)
    data = r.json()
    if data.get("videos"):
        video = random.choice(data["videos"])
        video_url = video["video_files"][0]["link"]
        return video_url
    return None

# 4️⃣ Create the YouTube Shorts video
def create_youtube_short(quote):
    # Pick a keyword from the quote
    keyword = quote.split()[0]
    video_url = get_video_url(keyword)
    if not video_url:
        print("⚠️ No video found, using fallback.")
        video_url = "https://player.vimeo.com/external/5184436.sd.mp4?s=default"  # fallback

    # Load video
    clip = VideoFileClip(video_url).subclip(0, 15)  # 15-second short

    # Create text overlay
    text_img_path = create_text_image(quote, size=(clip.w, clip.h))
    txt_clip = ImageClip(text_img_path).set_duration(clip.duration)

    # Composite video + text
    final_clip = CompositeVideoClip([clip, txt_clip])
    output_path = "/tmp/youtube_short.mp4"
    final_clip.write_videofile(output_path, fps=24)
    print(f"✅ Video saved: {output_path}")
    return output_path

# 5️⃣ Main
def main():
    quote = get_quote()
    print(f"💡 Selected quote: {quote}")
    create_youtube_short(quote)

if __name__ == "__main__":
    main()
