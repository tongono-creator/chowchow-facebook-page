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

# ── Dog breeds + Pexels queries ──────────────────────────────────────
# breed → Pexels query ที่ให้รูปตรงสายพันธุ์ที่สุด
DOG_BREEDS = {
    "Chow Chow":          "chow chow dog",
    "Golden Retriever":   "golden retriever dog",
    "Husky":              "husky dog",
    "Shiba Inu":          "shiba inu dog",
    "Corgi":              "corgi dog",
    "Pomeranian":         "pomeranian dog",
    "French Bulldog":     "french bulldog dog",
    "Labrador":           "labrador retriever dog",
    "Beagle":             "beagle dog",
    "Border Collie":      "border collie dog",
    "Dachshund":          "dachshund dog",
    "Poodle":             "poodle dog",
    "Samoyed":            "samoyed dog",
    "Maltese":            "maltese dog",
    "Shih Tzu":           "shih tzu dog",
    "Australian Shepherd":"australian shepherd dog",
    "Akita":              "akita dog",
    "Great Dane":         "great dane dog",
    "Dalmatian":          "dalmatian dog",
    "Doberman":           "doberman dog",
}

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
def get_pexels_image(query):  # query = ชื่อสายพันธุ์ตรงๆ
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


# ── Gemini Vision — verify + vibe ────────────────────────────────────
def analyze_image(img_path, expected_breed):
    """ยืนยันว่ารูปมีสุนัขจริง + detect actual breed + จับ personality/vibe
    คืน (has_dog: bool, actual_breed: str, vibe: str)
    """
    with open(img_path, "rb") as f:
        img_data = f.read()

    prompt = (
        f"รูปนี้คาดว่าเป็น {expected_breed}\n"
        "ตอบ 3 อย่าง แยกด้วย | :\n"
        "1. มีสุนัขในรูปไหม? ตอบ yes หรือ no\n"
        "2. สายพันธุ์จริงในรูปคืออะไร ตอบชื่อภาษาอังกฤษ เช่น Golden Retriever, Chow Chow, Husky, Samoyed\n"
        "   ถ้าไม่แน่ใจ ตอบว่า Mixed หรือ Unknown\n"
        "3. personality/vibe ของสุนัขในรูปนี้ เหมือนคนไทยนึกถึง เช่น: "
        "'เจ้าของบ้าน vibes', 'เด็กดื้อที่แม่รัก', 'rich kid', 'นักกีฬา', 'พนักงานออฟฟิศที่เบื่องาน', 'เด็กติดแม่'\n"
        "ตัวอย่าง: yes|Golden Retriever|เด็กดื้อที่แม่รัก\n"
        "ถ้าไม่มีสุนัข: no|none|ไม่มีสุนัข"
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
            parts = [p.strip() for p in result.split("|")]
            has_dog      = parts[0].lower() == "yes" if parts else False
            actual_breed = parts[1] if len(parts) > 1 else expected_breed
            vibe         = parts[2] if len(parts) > 2 else ""
            # ถ้า Vision บอกไม่มีสุนัข หรือ breed = none → return early
            if not has_dog or actual_breed.lower() in ("none", ""):
                return False, expected_breed, ""
            return has_dog, actual_breed, vibe
        except Exception as e:
            print(f"[{model}] vision failed: {e}")
    return False, expected_breed, ""


# ── Gemini Caption ────────────────────────────────────────────────────
def generate_hook(dog_breed, vibe, content_type):
    vibe_line = f"personality ที่เห็นในรูป: {vibe}" if vibe else ""
    prompt = (
        f"สุนัข: {dog_breed}\n"
        f"{vibe_line}\n"
        "เขียน hook text สั้นๆ ภาษาไทย สำหรับใส่บนรูป\n"
        "เขียนเหมือนคนพิมพ์เองใน Facebook ไม่ใช่นักการตลาด\n"
        "ภาษาพูดธรรมดา ความคิดแรกที่นึกได้ ไม่ประดิษฐ์\n"
        "บรรทัด 1: hook 3-5 คำ เล่นกับ personality ของหมาตัวนี้\n"
        "บรรทัด 2: คำถาม/ประโยคสั้น 4-7 คำ\n"
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


def make_caption(dog_breed, vibe, content_type):
    vibe_line = f"personality ที่เห็นในรูป: {vibe}" if vibe else ""
    prompt = (
        f"สุนัข: {dog_breed}\n"
        f"{vibe_line}\n"
        f"รูปแบบ content: {content_type}\n\n"
        "เขียนเหมือนคนพิมพ์เองใน Facebook ไม่ใช่นักการตลาด\n"
        "ภาษาพูดธรรมดา ไม่ประดิษฐ์ ไม่คำคม\n"
        "เล่นกับ personality ของหมาตัวนี้ ให้คนอ่านแล้วนึกถึงหมาที่บ้านตัวเอง\n\n"
        "เขียน Facebook caption สำหรับเพจ 'Chow Chow' (ความรู้/ความน่ารักของหมา):\n"
        "บรรทัด 1: hook ที่ตรงใจคนเลี้ยงหมา ไม่เกิน 40 ตัวอักษร\n"
        "บรรทัด 2-3: ข้อมูล/สิ่งที่น่ารู้เกี่ยวกับสายพันธุ์นี้ สั้นกระชับ\n"
        "บรรทัด 4: hashtag 3-4 อัน (#สุนัข #หมา ใส่ชื่อสายพันธุ์ด้วย)\n"
        "ห้ามใช้ ** markdown ตอบแค่ caption"
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

    for attempt in range(4):
        content_type = random.choice(CONTENT_TYPES)

        # 1. เลือก breed ก่อน → search Pexels ด้วย breed นั้น (รูปตรงกับ caption การันตี)
        breed_name, pexels_query = random.choice(list(DOG_BREEDS.items()))
        print(f"Breed: {breed_name} | Type: {content_type} | Attempt {attempt+1}")

        img_url, credit = get_pexels_image(pexels_query)

        # Reddit fallback (ถ้า Pexels ไม่มีผล)
        from_reddit = False
        if not img_url:
            print("Falling back to Reddit...")
            img_url, credit = get_reddit_image()
            from_reddit = True

        if not img_url:
            continue

        img_path = download_image(img_url)
        if not img_path:
            continue

        # 2. Vision ยืนยัน + detect actual breed + จับ personality/vibe
        has_dog, actual_breed, vibe = analyze_image(img_path, breed_name)
        if not has_dog:
            print("No dog in image, retrying...")
            os.unlink(img_path)
            continue

        # ถ้าเป็น Reddit fallback → ใช้ breed ที่ Vision detect จริง
        # (ป้องกัน caption พูดถึง Chow Chow แต่รูปเป็น Golden Retriever)
        if from_reddit and actual_breed and actual_breed.lower() not in ("unknown", "mixed"):
            print(f"Reddit fallback: switching breed {breed_name} → {actual_breed}")
            breed_name = actual_breed

        print(f"Breed (final): {breed_name} | Vibe: {vibe}")
        line1, line2 = generate_hook(breed_name, vibe, content_type)
        print(f"Hook: {line1} | {line2}")

        try:
            from overlay_utils import add_overlay
            overlaid = add_overlay(img_path, line1, line2, ACCENT_COLOR)
            os.unlink(img_path)
            img_path = overlaid
        except Exception as e:
            print(f"Overlay failed (using original): {e}")

        caption = make_caption(breed_name, vibe, content_type)
        if credit:
            caption += f"\n{credit}"
        print(f"Caption:\n{caption}\n")

        post_photo(caption, img_path)
        return

    print("Failed after 4 attempts")


if __name__ == "__main__":
    main()
