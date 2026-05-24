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

# ── Chow Chow Pexels queries — ใช้ query หลากหลายให้รูปไม่ซ้ำ ─────────
CHOWCHOW_PEXELS_QUERIES = [
    "chow chow dog",
    "chow chow puppy",
    "chow chow fluffy dog",
    "chow chow portrait",
    "chow chow cute",
]

# ── Chow Chow knowledge topics — หัวข้อที่คนเลี้ยง Chow Chow อยากรู้ ──
CHOWCHOW_TOPICS = {
    "ขน": {
        "topic": "การดูแลขน Chow Chow",
        "hook_style": "tip ดูแลขน",
        "caption_type": "tips",
    },
    "อาหาร": {
        "topic": "อาหารสำหรับ Chow Chow",
        "hook_style": "เตือนอาหารต้องห้าม",
        "caption_type": "ความรู้",
    },
    "นิสัย": {
        "topic": "พฤติกรรมและนิสัย Chow Chow",
        "hook_style": "เปิดโปงนิสัยจริง",
        "caption_type": "น่ารู้",
    },
    "สุขภาพ": {
        "topic": "โรคที่พบบ่อยใน Chow Chow",
        "hook_style": "เตือนสุขภาพ",
        "caption_type": "เตือนภัย",
    },
    "ฝึก": {
        "topic": "วิธีฝึก Chow Chow ที่ดื้อ",
        "hook_style": "tip ฝึกหมา",
        "caption_type": "tips",
    },
    "อากาศ": {
        "topic": "Chow Chow กับอากาศร้อนของไทย",
        "hook_style": "เตือนร้อน",
        "caption_type": "เตือนภัย",
    },
    "ลิ้นม่วง": {
        "topic": "ทำไม Chow Chow ถึงมีลิ้นสีม่วง",
        "hook_style": "fact แปลก",
        "caption_type": "น่ารู้",
    },
    "ค่าใช้จ่าย": {
        "topic": "ค่าใช้จ่ายจริงของการเลี้ยง Chow Chow",
        "hook_style": "เปิดตัวเลขจริง",
        "caption_type": "ความรู้",
    },
    "อาบน้ำ": {
        "topic": "ความถี่และวิธีอาบน้ำ Chow Chow",
        "hook_style": "tip อาบน้ำ",
        "caption_type": "tips",
    },
    "สังคม": {
        "topic": "Chow Chow กับคนแปลกหน้าและสัตว์อื่น",
        "hook_style": "เตือนพฤติกรรม",
        "caption_type": "น่ารู้",
    },
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

# ── Meme subreddits — chowchow weighted 3x, สัตว์อื่นแซม ──────────────
MEME_SUBREDDITS = [
    "chowchow", "chowchow", "chowchow",   # Chow Chow หลัก
    "WhatsWrongWithYourDog",
    "AnimalsBeingDerps",
    "dogmemes",
    "dogswithjobs",
    "rarepuppers",
    "WhatsWrongWithYourCat",
    "AnimalsBeingFunny",
    "AnimalsBeingBros",
    "aww",
]


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


# ── Reddit (fallback / meme) ──────────────────────────────────────────
def get_reddit_image(subreddit_pool=None):
    subreddit = random.choice(subreddit_pool or SUBREDDITS)
    url = f"https://www.reddit.com/r/{subreddit}/hot.rss"
    try:
        resp = requests.get(url, headers=HEADERS, timeout=10)
        resp.raise_for_status()
        root    = ET.fromstring(resp.content)
        ns      = {"atom": "http://www.w3.org/2005/Atom"}
        entries = root.findall("atom:entry", ns)
        image_posts = []
        for entry in entries:
            title_r   = entry.findtext("atom:title", "", ns).strip()
            content   = entry.findtext("atom:content", "", ns)
            img_urls  = re.findall(r'https?://[^\s"<>]+\.(?:jpg|jpeg|png|gif|webp)', content or "")
            good_imgs = [u for u in img_urls if "i.redd.it" in u or "imgur.com" in u]
            if good_imgs:
                image_posts.append({"url": good_imgs[0], "subreddit": subreddit, "title": title_r})
        if not image_posts:
            return None, None, None
        post = random.choice(image_posts[:10])
        return post["url"], f"📷 via r/{subreddit}", post["title"]
    except Exception as e:
        print(f"Reddit error ({subreddit}): {e}")
        return None, None, None


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


# ── Gemini Vision — verify Chow Chow + vibe ──────────────────────────
def analyze_image(img_path, reddit_title=""):
    """ยืนยันว่ารูปเป็น Chow Chow จริง + จับ personality/vibe
    คืน (is_chowchow: bool, vibe: str)
    ถ้าเป็นสายพันธุ์อื่น → return (False, "") เพื่อให้ main() retry รูปใหม่
    """
    with open(img_path, "rb") as f:
        img_data = f.read()

    title_ctx = f'ชื่อโพสต์ต้นฉบับ: "{reddit_title}"\n' if reddit_title else ""
    prompt = (
        f"{title_ctx}"
        "ตอบ 3 อย่าง แยกด้วย | :\n"
        "1. มีสุนัขในรูปไหม? ตอบ yes หรือ no\n"
        "2. สุนัขในรูปเป็น Chow Chow ไหม? ตอบ yes หรือ no\n"
        "   Chow Chow มีลักษณะ: ขนฟูมาก หน้าแบน ลิ้นสีม่วง/ดำ รูปร่างหมี\n"
        "   ถ้าไม่แน่ใจหรือเป็นสายพันธุ์อื่น (Husky, Samoyed, Pomeranian ฯลฯ) ตอบ no\n"
        "3. personality/vibe ของสุนัขในรูปนี้ เหมือนคนไทยนึกถึง เช่น: "
        "'เจ้าของบ้าน vibes', 'เด็กดื้อที่แม่รัก', 'rich kid', 'พนักงานออฟฟิศที่เบื่องาน'\n"
        "ตัวอย่าง: yes|yes|เจ้าของบ้าน vibes\n"
        "ถ้าไม่มีสุนัข: no|no|ไม่มีสุนัข"
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
            parts        = [p.strip() for p in result.split("|")]
            has_dog      = parts[0].lower() == "yes" if len(parts) > 0 else False
            is_chowchow  = parts[1].lower() == "yes" if len(parts) > 1 else False
            vibe         = parts[2] if len(parts) > 2 else ""
            if not has_dog:
                print("Vision: no dog")
                return False, ""
            if not is_chowchow:
                print("Vision: not Chow Chow — skipping")
                return False, ""
            return True, vibe
        except Exception as e:
            print(f"[{model}] vision failed: {e}")
    return False, ""


# ── Gemini Caption ────────────────────────────────────────────────────
def generate_hook(vibe, topic_data, reddit_title=""):
    """hook text สำหรับ knowledge mode — ใช้ topic_data ให้ตรงหัวข้อ"""
    vibe_line  = f"personality ที่เห็นในรูป: {vibe}" if vibe else ""
    title_line = f'ชื่อโพสต์ต้นฉบับ: "{reddit_title}"' if reddit_title else ""
    prompt = (
        f"สุนัข: Chow Chow\n"
        f"หัวข้อ content: {topic_data['topic']}\n"
        f"สไตล์: {topic_data['hook_style']}\n"
        f"{vibe_line}\n"
        f"{title_line}\n"
        "เขียน hook text สั้นๆ ภาษาไทย สำหรับใส่บนรูป\n"
        "เขียนเหมือนคนพิมพ์เองใน Facebook ไม่ใช่นักการตลาด\n"
        "ภาษาพูดธรรมดา ความคิดแรกที่นึกได้ ไม่ประดิษฐ์\n"
        "บรรทัด 1: hook 3-5 คำ เล่นกับหัวข้อ+สไตล์ที่กำหนด\n"
        "บรรทัด 2: คำถาม/ประโยคสั้น 4-7 คำ ให้คนอยากอ่านต่อ\n"
        "ตอบแค่ 2 บรรทัด ไม่มี hashtag ไม่มี **"
    )
    for model in TEXT_MODELS:
        try:
            resp = client.models.generate_content(model=model, contents=prompt)
            lines = clean_text(resp.text.strip()).split("\n")
            lines = [l.strip() for l in lines if l.strip()]
            return lines[0] if lines else "Chow Chow", lines[1] if len(lines) > 1 else ""
        except Exception as e:
            print(f"[{model}] hook failed: {e}")
    return "Chow Chow", ""


def make_caption(vibe, topic_data, reddit_title=""):
    """caption ให้ความรู้เรื่อง Chow Chow — ใช้ topic_data กำหนดหัวข้อ"""
    vibe_line  = f"personality ที่เห็นในรูป: {vibe}" if vibe else ""
    title_line = f'ชื่อโพสต์ต้นฉบับ: "{reddit_title}"' if reddit_title else ""
    prompt = (
        f"สุนัข: Chow Chow\n"
        f"หัวข้อ: {topic_data['topic']}\n"
        f"รูปแบบ content: {topic_data['caption_type']}\n"
        f"{vibe_line}\n"
        f"{title_line}\n\n"
        "เขียน Facebook caption แบบ ▪️ bullet narrative ให้ความรู้เรื่อง Chow Chow\n"
        "เขียนเหมือนคนที่รักและเลี้ยง Chow Chow จริงๆ ภาษาพูดธรรมดา ไม่ประดิษฐ์\n"
        "ใช้ ▪️ นำหน้าทุก bullet — 6-8 จุด เล่าเรื่องมีความต่อเนื่อง\n"
        "โครงสร้าง:\n"
        "▪️ 1-2: Setup — เหตุการณ์/สถานการณ์ที่คนเลี้ยง Chow Chow เจอจริง\n"
        "▪️ 3-4: Knowledge — ข้อมูล/tips เกี่ยวกับหัวข้อนี้ มีประโยชน์จริง ใส่ตัวเลขถ้ามี\n"
        "▪️ 5-6: Insight — สิ่งที่คนเลี้ยงมักไม่รู้หรือ 'โอ้โห จริงด้วย'\n"
        "▪️ 7-8: Engage — คำถามชวน comment หรือให้แชร์ประสบการณ์\n"
        "แต่ละ bullet: 1-2 ประโยค คนเลี้ยงอ่านแล้ว 'ใช่เลย' ได้\n"
        "จบด้วย hashtag 3-4 อัน เช่น #ChowChow #เลี้ยงChowChow #สุนัข\n"
        "ห้ามใช้ ** markdown ตอบแค่ caption"
    )
    for model in TEXT_MODELS:
        try:
            resp = client.models.generate_content(model=model, contents=prompt)
            return clean_text(resp.text.strip())
        except Exception as e:
            print(f"[{model}] caption failed: {e}")
    return "Chow Chow น่ารักมาก\n#ChowChow #สุนัข #เลี้ยงหมา"


def analyze_meme_image(img_path, reddit_title=""):
    """วิเคราะห์รูปตลก/สัตว์ → คืน (subject, vibe) — ไม่จำเป็นต้องเป็นหมา"""
    with open(img_path, "rb") as f:
        img_data = f.read()
    title_ctx = f'ชื่อโพสต์ต้นฉบับ: "{reddit_title}"\n' if reddit_title else ""
    prompt = (
        f"{title_ctx}"
        "ดูรูปนี้เหมือนคนไทยเล่น Facebook ไม่ใช่ AI วิเคราะห์ภาพ\n"
        "ตอบ 2 อย่าง แยกด้วย | :\n"
        "1. สัตว์/ตัวละครในรูปคืออะไร เช่น หมา Chow Chow, แมวส้ม, หมาทำหน้าตลก สั้นๆ 1-5 คำ\n"
        "2. ความตลก/vibe ที่เห็น เช่น: "
        "'หน้าขำมากดูไม่น่าเชื่อ', 'หน้าเบื่อโลก', 'เจ้าของบ้าน vibes', 'พระเอกที่โดนทิ้ง', "
        "'กำลังตั้งใจทำอะไรบางอย่าง', 'ไม่รู้ว่าทำไมทำแบบนี้', 'เด็กดื้อที่แม่รัก'\n"
        "ถ้าไม่มีสัตว์น่าสนใจ: ไม่เกี่ยว|ไม่เกี่ยว"
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
            print(f"Meme Vision: {result}")
            parts = [p.strip() for p in result.split("|")]
            subject = parts[0] if parts else ""
            vibe    = parts[1] if len(parts) > 1 else ""
            return subject, vibe
        except Exception as e:
            print(f"[{model}] meme vision failed: {e}")
    return "", ""


def generate_meme_hook(subject, vibe):
    """hook text แนวตลก/กวน สำหรับ meme mode"""
    prompt = (
        f"สัตว์: {subject}\n"
        f"vibe ที่เห็น: {vibe}\n"
        "เขียน hook text สั้น ภาษาไทย แนวตลก/กวน/แซว สำหรับใส่บนรูป\n"
        "เหมือนคนพิมพ์มุกเองใน Facebook ไม่ใช่นักการตลาด\n"
        "บรรทัด 1: มุก/hook 3-5 คำ ตรงๆ ไม่ประดิษฐ์\n"
        "บรรทัด 2: ต่อมุก/ชวนคอมเม้น 4-6 คำ\n"
        "ตอบแค่ 2 บรรทัด ไม่มี hashtag ไม่มี **"
    )
    for model in TEXT_MODELS:
        try:
            resp = client.models.generate_content(model=model, contents=prompt)
            lines = clean_text(resp.text.strip()).split("\n")
            lines = [l.strip() for l in lines if l.strip()]
            return lines[0] if lines else subject[:20], lines[1] if len(lines) > 1 else ""
        except Exception as e:
            print(f"[{model}] meme hook failed: {e}")
    return subject[:20], ""


def generate_meme_caption(subject, vibe, subreddit):
    """caption แนวตลก/แซว สำหรับ meme mode"""
    prompt = (
        f"สัตว์: {subject} | vibe: {vibe}\n"
        "เขียน Facebook caption แนวตลก/แซว เหมือน comment ไวรัลในเพจสัตว์เลี้ยง\n"
        "เหมือนคนพิมพ์เองใน Facebook ไม่ใช่นักการตลาด ไม่คำคม ไม่ประดิษฐ์\n"
        "สั้น กระแทก มีความ 'อิหยังวะ' หรือ relatable คนเลี้ยงหมา\n"
        "บรรทัด 1: มุก/caption ไม่เกิน 50 ตัวอักษร\n"
        "บรรทัด 2: ต่อมุกหรือชวนคอมเม้น\n"
        "บรรทัด 3: hashtag 2-3 อัน เช่น #หมา #ChoochBoy #เพื่อนซี้สี่ขา\n"
        "ห้ามใช้ ** ตอบแค่ caption"
    )
    for model in TEXT_MODELS:
        try:
            resp = client.models.generate_content(model=model, contents=prompt)
            return clean_text(resp.text.strip())
        except Exception as e:
            print(f"[{model}] meme caption failed: {e}")
    return f"{subject}\n#หมา #สัตว์เลี้ยง"


def handle_meme():
    """Meme mode — ดึงรูปตลกจาก MEME_SUBREDDITS (Chow Chow weighted) → caption ขำ"""
    print("=== Meme Mode ===")
    for attempt in range(5):
        img_url, credit, reddit_title = get_reddit_image(subreddit_pool=MEME_SUBREDDITS)
        if not img_url:
            print(f"Meme attempt {attempt+1}: no image")
            continue

        img_path = download_image(img_url)
        if not img_path:
            continue

        subject, vibe = analyze_meme_image(img_path, reddit_title=reddit_title)
        if not subject or "ไม่เกี่ยว" in subject:
            print("Meme: not interesting, skipping...")
            os.unlink(img_path)
            continue

        print(f"Subject: {subject} | Vibe: {vibe}")
        line1, line2 = generate_meme_hook(subject, vibe)
        print(f"Hook: {line1} | {line2}")

        try:
            from overlay_utils import add_overlay
            overlaid = add_overlay(img_path, line1, line2, ACCENT_COLOR)
            os.unlink(img_path)
            img_path = overlaid
        except Exception as e:
            print(f"Overlay failed: {e}")

        # ดึง subreddit name จาก credit
        sub = credit.split("r/")[-1] if credit and "r/" in credit else "animals"
        caption = generate_meme_caption(subject, vibe, sub)
        if credit:
            caption += f"\n{credit}"
        print(f"Caption:\n{caption}\n")

        post_photo(caption, img_path)
        return

    print("Meme mode: no suitable image after 5 attempts")


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

    # 30% meme mode, 70% dog breed knowledge mode
    if random.random() < 0.30:
        handle_meme()
        return

    for attempt in range(4):
        # 1. สุ่ม topic + Pexels query — Chow Chow เท่านั้น
        topic_key, topic_data = random.choice(list(CHOWCHOW_TOPICS.items()))
        pexels_query = random.choice(CHOWCHOW_PEXELS_QUERIES)
        print(f"Topic: {topic_key} ({topic_data['topic']}) | Attempt {attempt+1}")

        img_url, credit = get_pexels_image(pexels_query)

        # Reddit fallback — ใช้ chowchow subreddit เท่านั้น (ไม่ให้รูปผิดสายพันธุ์)
        reddit_title = ""
        if not img_url:
            print("Falling back to Reddit (chowchow)...")
            img_url, credit, reddit_title = get_reddit_image(subreddit_pool=["chowchow", "chowchow", "chowchow", "dogs"])

        if not img_url:
            continue

        img_path = download_image(img_url)
        if not img_path:
            continue

        # 2. Vision ยืนยันว่ามีสุนัขจริง + จับ personality/vibe
        has_dog, vibe = analyze_image(img_path, reddit_title=reddit_title)
        if not has_dog:
            print("No dog in image, retrying...")
            os.unlink(img_path)
            continue

        print(f"Vibe: {vibe}")
        line1, line2 = generate_hook(vibe, topic_data, reddit_title=reddit_title)
        print(f"Hook: {line1} | {line2}")

        try:
            from overlay_utils import add_overlay
            overlaid = add_overlay(img_path, line1, line2, ACCENT_COLOR)
            os.unlink(img_path)
            img_path = overlaid
        except Exception as e:
            print(f"Overlay failed (using original): {e}")

        caption = make_caption(vibe, topic_data, reddit_title=reddit_title)
        if credit:
            caption += f"\n{credit}"
        print(f"Caption:\n{caption}\n")

        post_photo(caption, img_path)
        return

    print("Failed after 4 attempts")


if __name__ == "__main__":
    main()
