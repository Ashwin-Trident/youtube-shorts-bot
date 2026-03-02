import os
import requests
from moviepy.editor import VideoFileClip, CompositeVideoClip
from moviepy.video.tools.drawing import color_gradient
from moviepy.video.VideoClip import TextClip
from PIL import Image, ImageDraw, ImageFont

OUTPUT_FILE = "short.mp4"
VIDEO_DURATION = 15

PEXELS_API_KEY = os.getenv("PEXELS_API_KEY")  # GitHub secret

# -----------------------------
# Get a random quote (free)
# -----------------------------
def get_quote():
    try:
        r = requests.get("https://api.quotable.io/random", timeout=10)
        data = r.json()
        return f"{data['content']} — {data['author']}"
    except:
        return "Believe in yourself — Unknown"

# -----------------------------
# Get free stock video from Pexels
# -----------------------------
def get_video_url(keyword="nature"):
    headers = {"Authorization": PEXELS_API_KEY}
    params = {"query": keyword, "orientation": "portrait", "size": "medium", "per_page": 1}
    try:
        r = requests.get("https://api.pexels.com/videos/search", headers=headers, params=params, timeout=10)
        data = r.json()
        if data["videos"]:
            return data["videos"][0]["video_files"][0]["link"]
    except:
        pass
    # fallback
    return "https://player.vimeo.com/external/5184436.hd.mp4?s=example"

# -----------------------------
# Download video
# -----------------------------
def download_video(url, filename="video.mp4"):
    r = requests.get(url, stream=True)
    with open(filename, "wb") as f:
        for chunk in r.iter_content(chunk_size=8192):
            f.write(chunk)
    return filename

# -----------------------------
# Create text image with Pillow
# -----------------------------
def create_text_image(text, size=(720, 1280), fontsize=60):
    img = Image.new("RGBA", size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    try:
        font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", fontsize)
    except:
        font = ImageFont.load_default()
    w, h = draw.textsize(text, font=font)
    draw.text(((size[0]-w)/2,(size[1]-h)/2), text, font=font, fill="white")
    path = "text.png"
    img.save(path)
    return path

# -----------------------------
# Create YouTube Short
# -----------------------------
def create_youtube_short(quote, video_file):
    clip = VideoFileClip(video_file).subclip(0, VIDEO_DURATION)

    # Create Pillow-based text image
    text_img_path = create_text_image(quote, size=(clip.w, clip.h))
    txt_clip = TextClip(text_img_path, method="caption").set_duration(clip.duration).set_position("center")

    final_clip = CompositeVideoClip([clip, txt_clip])
    final_clip.write_videofile(OUTPUT_FILE, fps=24)
    print(f"✅ Video saved as {OUTPUT_FILE}")

# -----------------------------
# Main
# -----------------------------
def main():
    quote = get_quote()
    print("💡 Selected quote:", quote)

    keyword = quote.split()[0]  # first word
    video_url = get_video_url(keyword)
    video_file = download_video(video_url)

    create_youtube_short(quote, video_file)

if __name__ == "__main__":
    main()
