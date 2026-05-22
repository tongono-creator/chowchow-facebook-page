import os
import re
import random
import time
import requests
import tempfile
import xml.etree.ElementTree as ET
from google import genai
from google.genai import types

# ── Config ───────────────────────────────────────────────────────────
PAGE_ID           = "102319399434080"
PAGE_ACCESS_TOKEN = os.environ["CHOWCHOW_PAGE_ACCESS_TOKEN"]
GEMINI_API_KEY    = os.environ.get("GEMINI_API_KEY", "")
PEXELS_API_KEY    = os.environ["PEXELS_API_KEY"]

client       = genai.Client(api_key=GEMINI_API_KEY)
TEXT_MODELS  = ["gemini-2.5-flash", "gemini-3.5-flash"]
ACCENT_COLOR = (255, 215, 0)  # เหลือง #FFD700

HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; ChowChowBot/1.0; +github)"}

IMAGE_EXTS = (".jpg", ".jpeg", ".png", ".gif", ".webp")

# ── Pexels queries ────────────────────────────────────────────────────
PEXELS_QUERIES = [
    "chow chow dog",
    "fluffy dog cute",
    "dog pet cute",
    "puppy dog fluffy",
    "dog playing",
    "golden retriever dog",
    "husky dog",
    "dog portrait",
    "cute dog outdoor",
    "dog sleeping",
]

# ── Reddit Subreddits (fallback) ──────────────────────────────────────
SUBREDDITS = [
    "chowchow",
    "dogs",
    "rarepuppers",
    "aww",
    "dogpictures",
    "WhatsWrongWithYourDog",
    "AnimalsBeingBros",
]

CONTENT_TYPES = ["ความรู้", "tips", "น่ารู้", "เตือนภัย"]


# ── Pexels ────────────────────────────────────────────────────────────
def get_pexels_image(query):
    try:
        resp = requests.get(
            "https://api.pexels.com/v1/search",
            headers={"Authorization": PEXELS_API_KEY},
            params={"query": query, "per_page": 15, "orientation": "landscape"},
            timeout=10,
        )
        resp.raise_for_status()
        photos = resp.json().get("photos", [])
        if not photos:
            print(f"Pexels: no results for '{query}'")
            return None, None
        photo = random.choice(photos)
        print(f"Pexels: {photo['src']['large'][:60]}")
        return photo["src"]["large"], f"📷 Photo by {photo.get('photographer','Pexels')} via Pexels"
    except Exception as e:
        print(f"Pexels error: {e}")
        return None, None


# ── Reddit (fallback) ─────────────────────────────────────────────────
def get_reddit_image():
    subreddit = random.choice(SUBREDDITS)
    url = f"https://www.reddit.com/r/{subreddit}/hot.rss"
    try:
        resp = requests.get(url, headers=HEADERS, timeout=10)
        resp.raise_for_status()
        root    = ET.fromstring(resp.content)
        ns      = {"atom": "http://www.w3.org/2005/Atom"}
        entries = root.findall("atom:entry", ns)
        image_posts = []
        for entry in entries:
            content   = entry.findtext("atom:content", "", ns)
            img_urls  = re.findall(r'https?://[^\s"<>]+\.(?:jpg|jpeg|png|gif|webp)', content or "")
            good_imgs = [u for u in img_urls if "i.redd.it" in u or "imgur.com" in u]
            if good_imgs:
                image_posts.append({"url": good_imgs[0], "subreddit": subreddit})
        if not image_posts:
            return None, None
        post = random.choice(image_posts[:10])
        return post["url"], f"📷 via r/{subreddit}"
    except Exception as e:
        print(f"Reddit error ({subreddit}): {e}")
        return None, None


# ── Download ──────────────────────────────────────────────────────────
def download_image(url):
    MAX_BYTES = 4 * 1024 * 1024
    try:
        resp = requests.get(url, headers=HEADERS, timeout=15, stream=True)
        resp.raise_for_status()
        data = b""
        for chunk in resp.iter_content(chunk_size=65536):
            data += chunk
            if len(data) > MAX_BYTES:
                print("Image too large")
                return None
        suffix = ".jpg"
        for ext in IMAGE_EXTS:
            if url.lower().split("?")[0].endswith(ext):
                suffix = ext
                break
        tmp = tempfile.NamedTemporaryFile(suffix=suffix, delete=False)
        tmp.write(data)
        tmp.close()
        return tmp.name
    except Exception as e:
        print(f"Download failed: {e}")
        return None


# ── Gemini Vision — วิเคราะห์รูป ─────────────────────────────────────
def analyze_image(img_path):
    """ดูรูปว่าเป็นสุนัขสายพันธุ์อะไร"""
    with open(img_path, "rb") as f:
        img_data = f.read()

    prompt = (
        "ดูรูปนี้แล้วตอบสั้นๆ ว่าเป็นสุนัขสายพันธุ์อะไร ชื่อภาษาไทยหรืออังกฤษ 1-4 คำ "
        "เช่น 'Chow Chow', 'Golden Retriever', 'ลาบราดอร์' "
        "ถ้าไม่ใช่รูปสุนัข ตอบว่า 'ไม่ใช่สุนัข'"
    )

    for model in TEXT_MODELS:
        try:
            resp = client.models.generate_content(
                model=model,
                contents=[
                    types.Part.from_bytes(data=img_data, mime_type="image/jpeg"),
                    types.Part.from_text(text=prompt),
                ],
            )
            result = resp.text.strip()
            print(f"Vision: {result}")
            return result
        except Exception as e:
            print(f"[{model}] vision failed: {e}")
    return None


# ── Gemini Caption ────────────────────────────────────────────────────
def generate_hook(dog_breed, content_type):
    prompt = (
        f"สุนัขในรูป: {dog_breed} | เนื้อหา: {content_type}\n"
        "เขียน hook text สั้นๆ ภาษาไทย สำหรับใส่บนรูป\n"
        "บรรทัด 1: hook 3-5 คำ น่ารัก/น่าสนใจ หยุดนิ้วได้\n"
        "บรรทัด 2: ความรู้/คำถามสั้น 4-7 คำ\n"
        "ตอบแค่ 2 บรรทัด ไม่มี hashtag ไม่มี **"
    )
    for model in TEXT_MODELS:
        try:
            resp = client.models.generate_content(model=model, contents=prompt)
            lines = clean_text(resp.text.strip()).split("\n")
            lines = [l.strip() for l in lines if l.strip()]
            return lines[0] if lines else dog_breed[:20], lines[1] if len(lines) > 1 else ""
        except Exception as e:
            print(f"[{model}] hook failed: {e}")
    return dog_breed[:20], ""


def make_caption(dog_breed, content_type):
    prompt = (
        f"เขียน Facebook caption ภาษาไทย สำหรับเพจความรู้เรื่องสุนัข\n"
        f"สุนัขในรูป: {dog_breed}\n"
        f"รูปแบบ content: {content_type}\n"
        "บรรทัด 1: หัวข้อดึงดูดเกี่ยวกับสุนัขสายพันธุ์นี้ ไม่เกิน 40 ตัวอักษร\n"
        "บรรทัด 2-3: เนื้อหาสั้นกระชับ มีประโยชน์ เกี่ยวกับสายพันธุ์นี้\n"
        "บรรทัด 4: hashtag 3-4 อัน (#สุนัข #หมา ใส่ชื่อสายพันธุ์ด้วย)\n"
        "ห้ามใช้ ** markdown ตอบแค่ caption เลย"
    )
    for model in TEXT_MODELS:
        try:
            resp = client.models.generate_content(model=model, contents=prompt)
            return clean_text(resp.text.strip())
        except Exception as e:
            print(f"[{model}] caption failed: {e}")
    return f"{dog_breed}\n#สุนัข #หมา #เลี้ยงหมา"


def clean_text(text):
    text = text.replace("\\n", "\n")
    text = re.sub(r"\*\*(.+?)\*\*", r"\1", text)
    text = re.sub(r"\*(.+?)\*",     r"\1", text)
    text = re.sub(r"__(.+?)__",     r"\1", text)
    text = re.sub(r"_(.+?)_",       r"\1", text)
    text = re.sub(r"^#+\s*",        "",    text, flags=re.MULTILINE)
    return text.strip()


# ── Facebook ──────────────────────────────────────────────────────────
def post_photo(caption, img_path):
    try:
        api_url = f"https://graph.facebook.com/v21.0/{PAGE_ID}/photos"
        with open(img_path, "rb") as f:
            resp = requests.post(
                api_url,
                data={"message": caption, "access_token": PAGE_ACCESS_TOKEN},
                files={"source": ("photo.jpg", f, "image/jpeg")},
                timeout=60,
            )
        result = resp.json()
        if "id" in result:
            post_id = result.get("post_id") or result["id"]
            print(f"Posted: {post_id}")
            add_comment(post_id)
            return True
        else:
            print(f"Post failed: {result}")
            return False
    except Exception as e:
        print(f"Facebook error: {e}")
        return False
    finally:
        if img_path and os.path.exists(img_path):
            os.unlink(img_path)


# ── Comment ───────────────────────────────────────────────────────────
def add_comment(post_id):
    from affiliate_utils import get_all_comments
    comments = get_all_comments()
    delay0 = random.uniform(60, 180)
    print(f"Waiting {delay0:.0f}s before first comment...")
    time.sleep(delay0)
    for i, msg in enumerate(comments, 1):
        if isinstance(msg, dict):
            data = {"access_token": PAGE_ACCESS_TOKEN, "message": msg["message"]}
            if msg.get("picture_url"):
                data["attachment_url"] = msg["picture_url"]
        else:
            data = {"access_token": PAGE_ACCESS_TOKEN, "message": msg}
        resp = requests.post(
            f"https://graph.facebook.com/v21.0/{post_id}/comments",
            data=data,
        )
        result = resp.json()
        if "id" in result:
            print(f"Comment {i} added: {result['id']}")
        else:
            print(f"Comment {i} error: {result}")
        if i < len(comments):
            time.sleep(random.uniform(30, 90))


# ── Main ──────────────────────────────────────────────────────────────
def main():
    print("=== Chow Chow Bot ===")

    for attempt in range(3):
        content_type = random.choice(CONTENT_TYPES)
        query        = random.choice(PEXELS_QUERIES)
        print(f"Query: {query} | Type: {content_type} | Attempt {attempt+1}")

        # Pexels primary
        img_url, credit = get_pexels_image(query)

        # Reddit fallback
        if not img_url:
            print("Falling back to Reddit...")
            img_url, credit = get_reddit_image()

        if not img_url:
            continue

        img_path = download_image(img_url)
        if not img_path:
            continue

        # Vision วิเคราะห์ว่าเป็นสุนัขอะไร
        dog_breed = analyze_image(img_path)
        if not dog_breed or "ไม่ใช่สุนัข" in dog_breed:
            print("Not a dog image, retrying...")
            os.unlink(img_path)
            continue

        line1, line2 = generate_hook(dog_breed, content_type)
        print(f"Hook: {line1} | {line2}")

        try:
            from overlay_utils import add_overlay
            overlaid = add_overlay(img_path, line1, line2, ACCENT_COLOR)
            os.unlink(img_path)
            img_path = overlaid
        except Exception as e:
            print(f"Overlay failed (using original): {e}")

        caption = make_caption(dog_breed, content_type)
        if credit:
            caption += f"\n{credit}"
        print(f"Caption:\n{caption}\n")

        post_photo(caption, img_path)
        return

    print("Failed after 3 attempts")


if __name__ == "__main__":
    main()
