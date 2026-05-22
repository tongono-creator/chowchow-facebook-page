import os
import re
import random
import time
import requests
import tempfile
import xml.etree.ElementTree as ET
from google import genai

# ── Config ───────────────────────────────────────────────────────────
PAGE_ID           = "102319399434080"
PAGE_ACCESS_TOKEN = os.environ["CHOWCHOW_PAGE_ACCESS_TOKEN"]
GEMINI_API_KEY    = os.environ.get("GEMINI_API_KEY", "")
PEXELS_API_KEY    = os.environ["PEXELS_API_KEY"]

client      = genai.Client(api_key=GEMINI_API_KEY)
TEXT_MODELS = ["gemini-2.5-flash", "gemini-3.5-flash"]

HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; ChowChowBot/1.0; +github)"}

# ── Reddit Subreddits ─────────────────────────────────────────────────
SUBREDDITS = [
    "chowchow",
    "dogs",
    "rarepuppers",
    "aww",
    "dogpictures",
    "WhatsWrongWithYourDog",
    "AnimalsBeingBros",
]

IMAGE_EXTS = (".jpg", ".jpeg", ".png", ".gif", ".webp")

# ── Knowledge Topics ──────────────────────────────────────────────────
DOG_TOPICS = [
    ("การเลี้ยง Chow Chow",      "chow chow dog care"),
    ("อาหารที่สุนัขกินได้",       "dog safe food"),
    ("อาหารที่สุนัขกินไม่ได้",    "toxic food for dogs"),
    ("โรคที่พบบ่อยในสุนัข",       "common dog diseases"),
    ("วัคซีนสุนัข",               "dog vaccination"),
    ("การดูแลขนสุนัข",            "dog grooming fluffy"),
    ("พฤติกรรมสุนัข",             "dog behavior"),
    ("การฝึกสุนัข",               "dog training tips"),
    ("ดูแลฟันสุนัข",              "dog dental care"),
    ("สุนัขกับอากาศร้อน",         "dog heat safety summer"),
    ("Chow Chow นิสัย",          "chow chow personality"),
    ("การออกกำลังกายสุนัข",       "dog exercise tips"),
]

CONTENT_TYPES = ["ความรู้", "tips", "เตือนภัย", "น่ารู้"]


# ── Reddit ────────────────────────────────────────────────────────────
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
            title   = entry.findtext("atom:title", "", ns).strip()
            content = entry.findtext("atom:content", "", ns)
            img_urls  = re.findall(r'https?://[^\s"<>]+\.(?:jpg|jpeg|png|gif|webp)', content or "")
            good_imgs = [u for u in img_urls if "i.redd.it" in u or "imgur.com" in u]
            if good_imgs and title:
                image_posts.append({"url": good_imgs[0], "subreddit": subreddit})

        if not image_posts:
            print(f"[{subreddit}] no image posts")
            return None, None

        post = random.choice(image_posts[:10])
        print(f"Reddit: r/{subreddit} | {post['url'][:60]}")
        return post["url"], f"r/{subreddit}"

    except Exception as e:
        print(f"Reddit error ({subreddit}): {e}")
        return None, None


# ── Pexels fallback ───────────────────────────────────────────────────
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


# ── Download image ────────────────────────────────────────────────────
def download_image(url):
    MAX_BYTES = 4 * 1024 * 1024
    try:
        resp = requests.get(url, headers=HEADERS, timeout=15, stream=True)
        resp.raise_for_status()
        data = b""
        for chunk in resp.iter_content(chunk_size=65536):
            data += chunk
            if len(data) > MAX_BYTES:
                print("Image too large, skipping")
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


# ── Gemini Caption ────────────────────────────────────────────────────
def make_caption(topic_name, content_type):
    prompt = (
        f"เขียน Facebook caption ภาษาไทย สำหรับเพจสุนัข Chow Chow\n"
        f"หัวข้อ: {content_type}เรื่อง{topic_name}\n"
        "บรรทัด 1: หัวข้อดึงดูด ไม่เกิน 40 ตัวอักษร\n"
        "บรรทัด 2-3: เนื้อหาสั้นกระชับ มีประโยชน์\n"
        "บรรทัด 4: hashtag 3-4 อัน (#ChowChow #สุนัข)\n"
        "ห้ามใช้ ** markdown ตอบแค่ caption เลย"
    )
    for model in TEXT_MODELS:
        try:
            resp = client.models.generate_content(model=model, contents=prompt)
            return clean_text(resp.text.strip())
        except Exception as e:
            print(f"[{model}] caption failed: {e}")
    return f"{topic_name}\n#ChowChow #สุนัข #เลี้ยงหมา"


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

    topic_name, pexels_query = random.choice(DOG_TOPICS)
    content_type             = random.choice(CONTENT_TYPES)
    print(f"Topic: {topic_name} | Type: {content_type}")

    # 1. ดึงรูปจาก Pexels ก่อน (keyword ตรง)
    img_url, credit = get_pexels_image(pexels_query)

    # 2. fallback → Reddit
    if not img_url:
        print("Falling back to Reddit...")
        img_url, credit = get_reddit_image()

    if not img_url:
        print("No image found, aborting")
        return

    img_path = download_image(img_url)
    if not img_path:
        print("Download failed, aborting")
        return

    caption = make_caption(topic_name, content_type)
    if credit:
        caption += f"\n{credit}"
    print(f"Caption:\n{caption}\n")

    post_photo(caption, img_path)


if __name__ == "__main__":
    main()
