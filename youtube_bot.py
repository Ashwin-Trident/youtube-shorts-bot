# youtube_bot.py
import random
from moviepy.editor import TextClip, CompositeVideoClip, ColorClip
import os
import base64
from googleapiclient.discovery import build
from google.oauth2.credentials import Credentials
import tempfile

# -----------------------------
# 1. Random cartoon story generator
# -----------------------------
CHARACTERS = ["🐶 Doggo", "🐱 Kitty", "🦊 Foxy", "🐸 Froggy", "🐵 Monkey"]
ACTIONS = ["finds a treasure", "meets a friend", "jumps over a river", "discovers magic", "saves the day"]
LOCATIONS = ["in the forest", "on the mountain", "at the beach", "in the city", "under the stars"]

def generate_story():
    char = random.choice(CHARACTERS)
    action = random.choice(ACTIONS)
    location = random.choice(LOCATIONS)
    return f"{char} {action} {location}!"

# -----------------------------
# 2. Create animated video
# -----------------------------
def create_video(text, output_file="final.mp4"):
    w, h = 720, 1280  # YouTube Shorts 9:16
    duration = 6  # seconds per story
    
    # Background color (random pastel)
    bg_color = tuple(random.randint(100, 255) for _ in range(3))
    bg = ColorClip(size=(w,h), color=bg_color, duration=duration)

    # Text clip with animation
    txt_clip = TextClip(text, fontsize=60, color="black", size=(w-100, None), method='caption', align='center')
    txt_clip = txt_clip.set_position('center').set_duration(duration)

    # Combine clips
    video = CompositeVideoClip([bg, txt_clip])
    video.write_videofile(output_file, fps=24)
    print(f"✅ Video generated: {output_file}")
    return output_file

# -----------------------------
# 3. Upload to YouTube Shorts
# -----------------------------
def upload_to_youtube(video_file):
    token_b64 = os.getenv("TOKEN_JSON_B64")
    if not token_b64:
        raise Exception("ERROR: TOKEN_JSON_B64 secret is empty!")
    
    token_json = base64.b64decode(token_b64)
    creds_file = tempfile.NamedTemporaryFile(delete=False)
    creds_file.write(token_json)
    creds_file.close()

    creds = Credentials.from_authorized_user_file(creds_file.name, scopes=["https://www.googleapis.com/auth/youtube.upload"])
    youtube = build("youtube", "v3", credentials=creds)

    request = youtube.videos().insert(
        part="snippet,status",
        body={
            "snippet": {
                "title": "🎨 AI Cartoon Story Reel",
                "description": "Automatically generated cartoon story for YouTube Shorts!",
                "tags": ["cartoon", "story", "AI", "shorts"],
                "categoryId": "1"
            },
            "status": {"privacyStatus": "public"}
        },
        media_body=video_file
    )
    response = request.execute()
    print(f"✅ Video uploaded: {response.get('id')}")

# -----------------------------
# 4. Main function
# -----------------------------
def main():
    story = generate_story()
    print(f"💡 Generated story: {story}")
    video_file = create_video(story)
    upload_to_youtube(video_file)

if __name__ == "__main__":
    main()
