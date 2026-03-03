import os
import random
import tempfile
import textwrap
import requests
from moviepy.editor import VideoFileClip, ImageClip, CompositeVideoClip
from PIL import Image, ImageDraw, ImageFont

# YouTube API
import google.auth.transport.requests
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload


# 1️⃣ Get a Quote
def get_quote():
    try:
        r = requests.get("https://api.quotable.io/random", timeout=10)
        if r.status_code == 200:
            data = r.json()
            return f"{data['content']} — {data['author']}"
    except Exception:
        print("⚠️ Failed to get quote, using default.")
    default_quotes = [
        "Believe in yourself — Unknown",
        "Success comes from persistence — Unknown",
        "Every day is a new opportunity — Unknown",
    ]
    return random.choice(default_quotes)


# 2️⃣ Create text image overlay
def create_text_image(text, size=(1080, 1920), font_size=80):
    img = Image.new("RGBA", size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    # System font available on GitHub runners
    font = ImageFont.truetype(
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", font_size
    )

    wrapped_text = textwrap.fill(text, width=25)
    bbox = draw.multiline_textbbox((0, 0), wrapped_text, font=font, spacing=20)
    text_width = bbox[2] - bbox[0]
    text_height = bbox[3] - bbox[1]

    x = (size[0] - text_width) // 2
    y = (size[1] - text_height) // 2

    draw.multiline_text(
        (x, y),
        wrapped_text,
        font=font,
        fill="white",
        align="center",
        spacing=20,
    )

    path = "/tmp/text_overlay.png"
    img.save(path)
    return path


# 3️⃣ Get Pexels video URL (MP4 only)
def get_video_url(keyword="nature"):
    PEXELS_API_KEY = os.environ.get("PEXELS_API_KEY")
    if not PEXELS_API_KEY:
        print("❌ Missing PEXELS_API_KEY")
        return None

    headers = {"Authorization": PEXELS_API_KEY}
    params = {"query": keyword, "per_page": 10, "orientation": "portrait"}

    try:
        r = requests.get(
            "https://api.pexels.com/videos/search",
            headers=headers,
            params=params,
            timeout=10,
        )
        if r.status_code != 200:
            print("❌ Pexels API failed")
            return None

        data = r.json()
        if not data.get("videos"):
            return None

        video = random.choice(data["videos"])
        for file in video["video_files"]:
            if file["file_type"] == "video/mp4":
                return file["link"]

    except Exception:
        print("⚠️ Error fetching Pexels video")
    return None


# 4️⃣ Download video locally
def download_video(url):
    print("⬇️ Downloading video...")
    headers = {"User-Agent": "Mozilla/5.0"}
    response = requests.get(url, headers=headers, stream=True, timeout=30)
    if response.status_code != 200:
        raise Exception("Failed to download video")

    temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".mp4")
    for chunk in response.iter_content(chunk_size=1024 * 1024):
        if chunk:
            temp_file.write(chunk)
    temp_file.close()
    print("✅ Video downloaded:", temp_file.name)
    return temp_file.name


# 5️⃣ Create YouTube Short video
def create_youtube_short(quote):
    keyword = quote.split()[0]
    video_url = get_video_url(keyword)

    if not video_url:
        print("⚠️ No video found, using fallback.")
        video_url = "https://filesamples.com/samples/video/mp4/sample_640x360.mp4"

    local_video_path = download_video(video_url)

    print("🎬 Loading video...")
    clip = VideoFileClip(local_video_path)
    duration = min(15, clip.duration)
    clip = clip.subclip(0, duration)

    text_img_path = create_text_image(quote, size=(clip.w, clip.h))
    txt_clip = ImageClip(text_img_path).set_duration(clip.duration)

    final_clip = CompositeVideoClip([clip, txt_clip])

    output_path = "/tmp/youtube_short.mp4"
    print("🎞 Rendering video...")
    final_clip.write_videofile(
        output_path,
        fps=24,
        codec="libx264",
        audio=False,
        threads=2,
    )

    print(f"✅ Video saved: {output_path}")
    return output_path


# 6️⃣ Upload to YouTube
def upload_to_youtube(video_path, title, description):
    creds = Credentials(
        None,
        refresh_token=os.environ.get("REFRESH_TOKEN"),
        token_uri="https://oauth2.googleapis.com/token",
        client_id=os.environ.get("CLIENT_ID"),
        client_secret=os.environ.get("CLIENT_SECRET"),
        scopes=["https://www.googleapis.com/auth/youtube.upload"],
    )

    request = google.auth.transport.requests.Request()
    creds.refresh(request)

    youtube = build("youtube", "v3", credentials=creds)

    body = {
        "snippet": {
            "title": title,
            "description": description,
            "tags": ["motivation", "shorts"],
            "categoryId": "22",
        },
        "status": {"privacyStatus": "public"},
    }

    media = MediaFileUpload(video_path)
    request = youtube.videos().insert(part="snippet,status", body=body, media_body=media)
    response = request.execute()
    print("✅ Uploaded to YouTube!")
    print("Video URL: https://youtube.com/watch?v=" + response["id"])


# 7️⃣ Main
def main():
    quote = get_quote()
    print(f"💡 Selected quote: {quote}")

    video_path = create_youtube_short(quote)

    upload_to_youtube(
        video_path,
        title=quote + " #Shorts",
        description="Daily Motivation 💡\n\n#Shorts #Motivation",
    )


if __name__ == "__main__":
    main()
