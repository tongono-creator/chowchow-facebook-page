import sys
import io
import os
import re
import random
import time
import requests
import tempfile
import hashlib
import xml.etree.ElementTree as ET
from google import genai
from google.genai import types
from google.genai.types import HttpOptions

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

# ── Config ───────────────────────────────────────────────────────────
PAGE_ID           = "102319399434080"
PAGE_ACCESS_TOKEN = os.environ.get("CHOWCHOW_PAGE_ACCESS_TOKEN", "")
GEMINI_API_KEY    = os.environ.get("GEMINI_API_KEY", "")
PEXELS_API_KEY    = os.environ.get("PEXELS_API_KEY", "")

if not GEMINI_API_KEY:
    try:
        import sys
        sys.path.append(os.path.join(os.path.dirname(__file__), "..", "rocket-facebook-page"))
        from config import GOOGLE_API_KEY
        GEMINI_API_KEY = GOOGLE_API_KEY
    except Exception:
        pass

client       = genai.Client(api_key=GEMINI_API_KEY, http_options=HttpOptions(timeout=300000))
TEXT_MODELS       = ["gemini-1.5-flash", "gemini-1.5-flash"]
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

CHOWCHOW_TOPICS = {
    "อาหารอันตราย": {
        "topic": "อาหารที่เป็นพิษร้ายแรงต่อสุนัข เช่น ช็อกโกแลต องุ่น อะโวคาโด หอมใหญ่",
        "hook_style": "เตือนภัยอาหารอันตรายสำหรับสุนัข",
        "caption_type": "การให้ความรู้และข้อควรระวังเรื่องของกินมีพิษ",
    },
    "การหวีขนสองชั้น": {
        "topic": "วิธีการหวีและแปรงขนสุนัขขนหนาสองชั้นเพื่อป้องกันขนสังกะตังและช่วยระบายความร้อน",
        "hook_style": "เคล็ดลับการหวีขนสุนัขสองชั้นให้ถูกวิธี",
        "caption_type": "การแนะนำทริกการดูแลเส้นขนสุนัขสองชั้น",
    },
    "โรคผิวหนังอับชื้น": {
        "topic": "การป้องกันและระวังโรคผิวหนัง ยีสต์ เชื้อรา ที่เกิดจากความอับชื้นในสุนัขขนหนา",
        "hook_style": "เตือนภัยโรคผิวหนังจากความอับชื้น",
        "caption_type": "การให้ความรู้เรื่องการเป่าขนและรักษาผิวหนังให้แห้ง",
    },
    "โรคลมแดด": {
        "topic": "การป้องกันโรคลมแดดหรือฮีทสโตรก (Heatstroke) ในช่วงอากาศร้อนจัดของสุนัขหน้าสั้นขนหนา",
        "hook_style": "เตือนภัยโรคลมแดดสำหรับสุนัขหน้าสั้นขนหนา",
        "caption_type": "วิธีสังเกตอาการและปฐมพยาบาลเบื้องต้น",
    },
    "การดูแลช่องหู": {
        "topic": "วิธีทำความสะอาดช่องหูของสุนัขหูพับ/ขนหนาเพื่อป้องกันการสะสมสิ่งสกปรกและอักเสบ",
        "hook_style": "วิธีดูแลความสะอาดหูสุนัขไม่ให้อักเสบ",
        "caption_type": "ทริกการใช้ยาเช็ดหูและหลีกเลี่ยงความชื้น",
    },
    "ออกกำลังกายถนอมข้อต่อ": {
        "topic": "การออกกำลังกาย/พาเดินเล่นอย่างเหมาะสมเพื่อถนอมข้อต่อสะโพกและเข่าสุนัขพันธุ์ใหญ่กระดูกใหญ่",
        "hook_style": "ทริกการออกกำลังกายสุนัขพันธุ์ใหญ่เพื่อถนอมข้อต่อ",
        "caption_type": "ข้อควรระวังการกระโดดหรือวิ่งบนพื้นลื่น",
    },
    "กินน้ำสะอาด": {
        "topic": "ความสำคัญของการกินน้ำสะอาดอย่างเพียงพอเพื่อป้องกันการเกิดนิ่วและโรคไตในสุนัข",
        "hook_style": "เตือนความสำคัญของการดื่มน้ำให้เพียงพอ",
        "caption_type": "เคล็ดลับกระตุ้นสุนัขดื่มน้ำและเลือกชามน้ำที่สะอาด",
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


# ── History Helper ───────────────────────────────────────────────────
HISTORY_FILE = "posted_history.txt"

def load_history():
    if os.path.exists(HISTORY_FILE):
        try:
            with open(HISTORY_FILE, "r", encoding="utf-8") as f:
                return [line.strip() for line in f if line.strip()]
        except Exception:
            return []
    return []

def save_to_history(item):
    items = load_history()
    items.append(item)
    items = items[-500:] # Cap history
    try:
        with open(HISTORY_FILE, "w", encoding="utf-8") as f:
            for it in items:
                f.write(it + "\n")
    except Exception as e:
        print(f"Error saving history: {e}")

def reddit_title_key(title):
    """Stable dedup key for a Reddit post's identity (prefix 'title:').
    Catches reposts that reuse the same title/image under a new URL or headline."""
    norm = re.sub(r"[^\w฀-๿]+", "", (title or "").strip().lower())
    if not norm:
        return ""
    return "title:" + hashlib.md5(norm.encode("utf-8")).hexdigest()[:16]


# ── Pexels ────────────────────────────────────────────────────────────
def get_pexels_image(query):  # query = ชื่อสายพันธุ์ตรงๆ
    history = set(load_history())
    page = random.randint(1, 10)
    try:
        resp = requests.get(
            "https://api.pexels.com/v1/search",
            headers={"Authorization": PEXELS_API_KEY},
            params={"query": query, "per_page": 15, "page": page},
            timeout=10,
        )
        resp.raise_for_status()
        photos = resp.json().get("photos", [])
        if not photos:
            print(f"Pexels: no results for '{query}' page {page}")
            return None, None, None
        
        new_photos = [p for p in photos if (p["src"].get("large2x") or p["src"]["large"]) not in history]
        if not new_photos:
            print(f"Pexels: all photos on page {page} for query '{query}' already posted")
            return None, None, None

        photo   = random.choice(new_photos)
        img_url = photo["src"].get("large2x") or photo["src"]["large"]
        alt     = photo.get("alt", query)
        print(f"Pexels: alt='{alt[:60]}'")
        return img_url, f"📷 Photo by {photo.get('photographer','Pexels')} via Pexels", alt
    except Exception as e:
        print(f"Pexels error: {e}")
        return None, None, None


# ── Reddit (fallback / meme) ──────────────────────────────────────────
def get_reddit_image(subreddit_pool=None):
    history = set(load_history())
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
            good_imgs = [u for u in img_urls if ("i.redd.it" in u or "imgur.com" in u) and u not in history]
            if good_imgs and reddit_title_key(title_r) not in history:
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

    for model_idx, model in enumerate(TEXT_MODELS):
        if model_idx > 0:
            import time; time.sleep(2)
        try:
            contents = []
            if reddit_title:
                contents.append(types.Part.from_text(text=f'Photo title: "{reddit_title}"'))
            contents.append(types.Part.from_bytes(data=img_data, mime_type="image/jpeg"))
            contents.append(types.Part.from_text(text=prompt))
            resp = client.models.generate_content(model=model, contents=contents)
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
def clean_hook_lines(raw_text):
    text = clean_text(raw_text)
    
    # Check if we should split by pipe or newline
    if "|" in text:
        parts = text.split("|")
    else:
        parts = text.split("\n")
        
    # Pattern to strip prefixes like "บรรทัด 1: ", "ข้อความในโพสต์ Facebook: ", "1. ", etc.
    label_pattern = r'^(ข้อความในโพสต์\s*Facebook|Facebook\s*Caption|Facebook\s*caption|Caption|caption|ข้อความบนรูป|ข้อความในรูป|ข้อความ|คำบรรยาย|คำอธิบาย|บรรทัดที่\s*\d+|บรรทัด\s*\d+|ประโยคที่\s*\d+|ประโยค\s*\d+|Hook\s*text|Hook|Line\s*\d+|[L|l]ine\s*\d+|\d+)\s*[:\-\.\s]\s*'
    
    cleaned_lines = []
    for part in parts:
        cleaned = re.sub(label_pattern, '', part, flags=re.IGNORECASE).strip()
        cleaned = cleaned.strip('"\'“”‘’')
        if cleaned:
            cleaned_lines.append(cleaned)
            
    return cleaned_lines


def generate_hook(vibe, topic_data, reddit_title=""):
    """hook text สำหรับ knowledge mode — ใช้ topic_data ให้ตรงหัวข้อ"""
    vibe_line  = f"personality ที่เห็นในรูป: {vibe}" if vibe else ""
    title_line = f'ชื่อโพสต์ต้นฉบับ: "{reddit_title}"' if reddit_title else ""
    prompt = (
        f"สุนัข: Chow Chow\n"
        f"หัวข้อสติปันสาระความรู้: {topic_data['topic']}\n"
        f"สไตล์: {topic_data['hook_style']}\n"
        f"{vibe_line}\n"
        f"{title_line}\n"
        "เขียน hook text สั้นๆ ภาษาไทย สำหรับใส่บนรูป เพื่อให้ความรู้/เตือนภัยเกี่ยวกับการดูแลสุนัข โดยสวมบทบาทเป็นน้องหมา Chow Chow เพศผู้ (ชื่อแอดมินน้องตูบ) ลงท้ายคำว่า 'ฮะ' หรือ 'ครับ' หรือ 'โฮ่ง'\n"
        "เขียนจากมุมมองสุนัขเตือนภัยเงียบ หรือให้เกร็ดความรู้แสนรู้เกี่ยวกับความปลอดภัย/การดูแลตัวเอง ให้ทาสได้ฉุกคิดแบบขำขันและได้สาระ\n"
        "บรรทัด 1: คำเตือนภัยหรือความจริงที่น่าตกใจ 3-5 คำ (ลงท้ายด้วย ..)\n"
        "บรรทัด 2: ประโยคสรุปความรู้หรือคำถามจี้ใจ 4-7 คำ ที่ทำให้อยากอ่านทริกการดูแลในแคปชั่นต่อ\n"
        "ตอบเฉพาะข้อความพาดหัว 2 บรรทัด ไม่มี hashtag ไม่มี ** ไม่มีป้ายกำกับ เช่น 'บรรทัด 1:' หรือ 'Hook:' ใดๆ เด็ดขาด"
    )
    for model_idx, model in enumerate(TEXT_MODELS):
        if model_idx > 0:
            import time; time.sleep(2)
        try:
            resp = client.models.generate_content(model=model, contents=prompt)
            lines = clean_hook_lines(resp.text)
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
        f"หัวข้อความรู้: {topic_data['topic']}\n"
        f"รูปแบบ content: {topic_data['caption_type']}\n"
        f"{vibe_line}\n"
        f"{title_line}\n\n"
        "เขียน Facebook caption ให้ความรู้/เคล็ดลับสั้นๆ เกี่ยวกับการดูแลสุนัขสายพันธุ์ขนหนา/Chow Chow (เช่น ทำไมถึงห้ามกินองุ่น, วิธีแปรงขนสองชั้นที่ถูกต้อง, วิธีสังเกตฮีทสโตรก) เป็นข้อความ 1 ย่อหน้าสั้น (ความยาว 3-5 ประโยค) โดยสวมบทบาทเป็นแอดมินน้องหมา Chow Chow เพศผู้ (ชื่อแอดมินน้องตูบ) เล่าด้วยภาษาเป็นกันเอง แสนรู้ น่ารัก ลงท้ายด้วยคำว่า 'ฮะ' หรือ 'ครับ' หรือ 'โฮ่ง' เรียกแทนตัวเองว่า 'ผม' หรือ 'น้องตูบ'\n"
        "ห้ามเขียนในรูปแบบข้อตกลง หัวข้อย่อย หรือมีสัญลักษณ์นำหน้าบรรทัด เช่น ▪️ หรือ - เด็ดขาด\n"
        "โครงสร้างเนื้อหาต้องอ่านง่ายและได้สาระจริง: อธิบายข้อเท็จจริงแบบสั้นๆ จบด้วยคำแนะนำทริกการดูแล หรือการปฐมพยาบาลเบื้องต้น จากนั้นปิดท้ายชวนทาสหมาเข้ามาแชร์ประสบการณ์หรือบอกเล่าวิธีดูแลของบ้านตัวเอง (เช่น 'บ้านพี่ๆ มีวิธีระวังฮีทสโตรกยังไงบ้างฮะ?', 'เคยเกือบเผลอป้อนองุ่นให้เด็กๆ ไหมครับ?')\n"
        "จบด้วย hashtag 3-4 อัน เช่น #ChowChow #ความรู้เรื่องหมา #ดูแลสุนัข\n"
        "ห้ามใช้ ** markdown ตอบเฉพาะ caption ที่จัดเรียงเป็นย่อหน้าสั้นปกติชวนคุย"
    )
    for model_idx, model in enumerate(TEXT_MODELS):
        if model_idx > 0:
            import time; time.sleep(2)
        try:
            resp = client.models.generate_content(model=model, contents=prompt)
            return clean_text(resp.text.strip())
        except Exception as e:
            print(f"[{model}] caption failed: {e}")
    return "Chow Chow น่ารักมาก\n#ChowChow #สุนัข #เลี้ยงหมา"


def validate_meme_content(dog_role, line1, line2, caption):
    full_text = f"{line1} {line2} {caption}"
    
    # 1. Reject if caption contains hashtags in a list format, or if there's any list/bullet symbols
    for char in ["•", "▪️", "✅", "👉", "-", "*"]:
        if char in full_text:
            print(f"Meme Validation failed: Contains blacklisted symbol '{char}'")
            return False
            
    # Check for ordered list numbers (e.g. "1.", "2.", "3.")
    if re.search(r'\b\d+[\.\)\s\u200b]', full_text):
        print("Meme Validation failed: Contains ordered list numbers")
        return False
        
    # 2. If working_dog, reject if it uses naughty pet words
    if dog_role == "working_dog":
        for word in ["ซน", "ดื้อ", "ทำบ้านพัง", "ทาสปวดหัว", "ปวดหัว", "พังบ้าน"]:
            if word in full_text:
                print(f"Meme Validation failed: Working dog meme contains naughty pet word '{word}'")
                return False
        # Ensure it mentions something about sniffing/inspecting/eating/baggage
        keywords = ["ดม", "ตรวจ", "งาน", "ของกิน", "ขนม", "กระเป๋า", "หน้าที่", "K9", "สายตรวจ", "ด่าน"]
        if not any(k in full_text for k in keywords):
            print("Meme Validation failed: Working dog meme does not contain sniffing/working context keywords")
            return False
            
    # 3. Reject if caption uses broad questions that are not specific to the image
    broad_patterns = ["วีรกรรมอะไร", "ดื้อแบบไหน", "ทำอะไรกันอยู่", "ทาสปวดหัวกับอะไร"]
    for pat in broad_patterns:
        if pat in caption:
            print(f"Meme Validation failed: Caption contains generic broad question pattern '{pat}'")
            return False
            
    return True


def handle_meme(dry_run=False):
    """Meme mode — ดึงรูปตลกจาก MEME_SUBREDDITS (Chow Chow weighted) → caption ขำ"""
    import json
    print("=== Meme Mode ===")
    for attempt in range(5):
        img_url, credit, reddit_title = get_reddit_image(subreddit_pool=MEME_SUBREDDITS)
        if not img_url:
            print(f"Meme attempt {attempt+1}: no image")
            continue

        img_path = download_image(img_url)
        if not img_path:
            continue

        with open(img_path, "rb") as f:
            img_data = f.read()

        mime_type = "image/jpeg"
        if img_path.lower().endswith(".png"):
            mime_type = "image/png"
        elif img_path.lower().endswith(".webp"):
            mime_type = "image/webp"

        title_ctx = f'ชื่อโพสต์ต้นฉบับ: "{reddit_title}"\n' if reddit_title else ""
        prompt = (
            "นี่คือโพสต์รูปสัตว์เลี้ยง (สุนัขหรือแมว) จาก Reddit\n"
            f"{title_ctx}\n"
            "งานของคุณคือวิเคราะห์รูปภาพและจัดทำเนื้อหาสำหรับโพสต์บนเพจเฟซบุ๊กสุนัขแอดมินน้องตูบ Chow Chow เพศผู้ (โทนเสียง ขี้เล่น สุภาพ ลงท้าย ฮะ/ครับ/โฮ่ง เรียกตัวเองว่า ผม/น้องตูบ)\n\n"
            "กรุณาวิเคราะห์และตอบกลับในรูปแบบ JSON ตามกฎที่เคร่งครัดดังต่อไปนี้:\n"
            "1. **dog_role (การจำแนกบทบาทสุนัขในภาพ)**:\n"
            "   - 'pet' = สุนัขบ้านทั่วไป\n"
            "   - 'working_dog' = สุนัขทำงาน (เช่น K9, ด่านตรวจศุลกากร, สุนัขตำรวจ, กู้ภัย, บริการ)\n"
            "   - 'funny_pet' = สุนัขทำพฤติกรรมตลก/ประหลาดในบ้าน\n"
            "   - 'unknown' = สัตว์อื่น (แมว ฯลฯ) หรือไม่แน่ใจ\n"
            "2. **กฎห้ามขัดแย้งกับบทบาท (Role-Consistency Rule)**:\n"
            "   - หาก `dog_role` คือ `working_dog` ห้ามเขียนมุก/แคปชั่นในทำนอง 'หมาบ้านซน', 'หมาดื้อทำลายข้าวของ', หรือ 'ทาสปวดหัวกับวีรกรรมดื้อในบ้าน' เด็ดขาด! ให้เขียนแนว 'น้องกำลังปฏิบัติหน้าที่จริงจังเกินเหตุ', 'ตรวจหาของกิน', 'เจ้าหน้าที่สี่ขาทำงานสุดตัว'\n"
            "3. **ข้อความบนภาพ (image_hook_line1 และ image_hook_line2)**:\n"
            "   - ต้องสั้นมาก เข้าใจใน 1 วินาที (ไม่เกิน 12 คำภาษาไทยรวมกัน)\n"
            "   - ต้องเจาะจงกับสิ่งสำคัญที่เห็นในภาพและบริบทจริง (เช่น มีกระเป๋า ของกิน ด่านตรวจ ต้องพูดถึงเรื่องนั้น ห้ามพูดเรื่องกว้างๆ)\n"
            "   - `image_hook_line1`: ปูเรื่อง/Setup 3-5 คำ ลงท้ายด้วย ..\n"
            "   - `image_hook_line2`: หักมุม/Punchline ตลกกวนๆ 4-6 คำ เป็นเหมือนความคิดในหัวสุนัข/Inner Monologue\n"
            "   - ห้ามแต่งว่าสุนัขทำผิดหรือซนทำบ้านพังหากภาพคือหมาทำงานกู้ภัยหรือ K9 ทำด่านตรวจ\n"
            "4. **แคปชั่น (caption)**:\n"
            "   - ต้องเขียนเป็นย่อหน้าธรรมชาติเท่านั้น (Natural Paragraphs Only, 2-3 ย่อหน้าสั้น)\n"
            "   - ห้ามใช้ bullet point หรือรายการใดๆ เด็ดขาด (ห้ามมี •, ▪️, -, *, ✅, 👉 หรือตัวเลข 1. 2. 3.)\n"
            "   - ห้ามขึ้นบรรทัดใหม่ถี่ๆ แบบรายการ ให้เนื้อความยาวต่อเนื่องกันในย่อหน้าแบบที่คนพิมพ์เอง\n"
            "   - ภาษาที่ใช้เป็นน้องตูบเพศผู้สุภาพ ขี้เล่น เป็นกันเอง ลงท้าย ฮะ/ครับ/โฮ่ง\n"
            "   - เนื้อเรื่องแคปชั่นต้องเชื่อมโยงโดยตรงกับสถานการณ์ในภาพ ไม่พูดประเด็นกว้าง เช่น 'วีรกรรมของน้อง'\n"
            "   - ตอนท้ายแคปชั่น ต้องมีคำถามชวนให้ลูกเพจเข้ามาแชร์ประสบการณ์เกี่ยวกับเรื่องนี้ เช่น 'บ้านใครมีหมาดมขนมเก่งกว่าคนบ้างครับ?'\n"
            "   - จบด้วย hashtag 2-3 อันเกี่ยวเนื่องกันแบบไม่มีสัญลักษณ์ลิสต์นำหน้า\n\n"
            "กรุณาตอบเป็น JSON ในรูปแบบนี้เท่านั้น (ห้ามมี markdown codeblock หรือคำนำหน้าใดๆ):\n"
            "{\n"
            "  \"dog_role\": \"pet / working_dog / funny_pet / unknown\",\n"
            "  \"image_hook_line1\": \"...\",\n"
            "  \"image_hook_line2\": \"...\",\n"
            "  \"caption\": \"...\"\n"
            "}"
        )

        success_gen = False
        for model_idx, model in enumerate(TEXT_MODELS):
            if model_idx > 0:
                import time; time.sleep(2)
            try:
                resp = client.models.generate_content(
                    model=model,
                    contents=[
                        types.Part.from_bytes(data=img_data, mime_type=mime_type),
                        types.Part.from_text(text=prompt),
                    ],
                    config=types.GenerateContentConfig(
                        response_mime_type="application/json"
                    )
                )
                res_json = json.loads(resp.text.strip())
                dog_role = res_json.get("dog_role", "unknown").strip()
                line1 = res_json.get("image_hook_line1", "").strip()
                line2 = res_json.get("image_hook_line2", "").strip()
                caption = res_json.get("caption", "").strip()
                
                line1 = clean_text(line1)
                line2 = clean_text(line2)
                caption = clean_text(caption)
                
                print(f"Generated: Role={dog_role} | Hook='{line1}' / '{line2}'")
                
                if validate_meme_content(dog_role, line1, line2, caption):
                    success_gen = True
                    break
                else:
                    print("Validation failed, trying next model or retry...")
            except Exception as e:
                print(f"[{model}] meme generation failed: {e}")

        if not success_gen:
            print("Meme content generation failed or invalid for this image, skipping...")
            os.unlink(img_path)
            continue

        # Draw overlays
        try:
            from overlay_utils import add_overlay
            overlaid = add_overlay(img_path, line1, line2, ACCENT_COLOR)
            os.unlink(img_path)
            img_path = overlaid
        except Exception as e:
            print(f"Overlay failed: {e}")

        # Post or dry run
        full_caption = caption
        if credit:
            full_caption += f"\n{credit}"
        print(f"Caption:\n{full_caption}\n")

        if dry_run:
            print(f"[DRY RUN] Would post photo. File: {img_path}")
            if img_path and os.path.exists(img_path):
                os.unlink(img_path)
            return

        success = post_photo(full_caption, img_path)
        if success:
            save_to_history(img_url)
            if reddit_title:
                save_to_history(reddit_title_key(reddit_title))
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
            add_comment(post_id, caption=caption, img_path=img_path)
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
def add_comment(post_id, caption=None, img_path=None):
    from affiliate_utils import get_all_comments
    comments = get_all_comments(caption=caption, img_path=img_path)
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
            timeout=60,
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
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true", help="Run without posting to Facebook")
    parser.add_argument("--mode", choices=["breed", "meme"], help="Force specific mode")
    args = parser.parse_args()

    print("=== Chow Chow Bot ===")
    if args.dry_run:
        print("[DRY RUN MODE ACTIVE]")

    # Decide mode
    if args.mode == "meme":
        use_meme = True
    elif args.mode == "breed":
        use_meme = False
    else:
        use_meme = random.random() < 0.30

    if use_meme:
        handle_meme(dry_run=args.dry_run)
        return

    for attempt in range(4):
        # 1. สุ่ม topic + Pexels query — Chow Chow เท่านั้น
        topic_key, topic_data = random.choice(list(CHOWCHOW_TOPICS.items()))
        pexels_query = random.choice(CHOWCHOW_PEXELS_QUERIES)
        print(f"Topic: {topic_key} ({topic_data['topic']}) | Attempt {attempt+1}")

        img_url, credit, reddit_title = get_pexels_image(pexels_query)

        # Reddit fallback — ใช้ chowchow subreddit เท่านั้น (ไม่ให้รูปผิดสายพันธุ์)
        if not img_url:
            print("Falling back to Reddit (chowchow)...")
            img_url, credit, reddit_title = get_reddit_image(subreddit_pool=["chowchow", "chowchow", "chowchow", "dogs"])
            reddit_title = reddit_title or ""

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

        if args.dry_run:
            print(f"[DRY RUN] Would post photo. File: {img_path}")
            if img_path and os.path.exists(img_path):
                os.unlink(img_path)
            return

        success = post_photo(caption, img_path)
        if success:
            save_to_history(img_url)
            if reddit_title:
                save_to_history(reddit_title_key(reddit_title))
        return

    print("Failed after 4 attempts")


if __name__ == "__main__":
    main()
