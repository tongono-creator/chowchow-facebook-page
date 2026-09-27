# -*- coding: utf-8 -*-
"""dilemma.py — โพสต์การ์ดคำถามดราม่าและทางเลือกวัดใจคนรักหมาสไตล์ Threads เพจ Chow Chow"""

import os
import sys
import io
import re
import json
import time
import random
import requests
import hashlib
import xml.etree.ElementTree as ET
from PIL import Image, ImageDraw, ImageFont
from datetime import datetime, timezone, timedelta

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from google import genai
from google.genai import types
from google.genai.types import HttpOptions

# ── Config ───────────────────────────────────────────────────────────────────
PAGE_ID           = "102319399434080"
PAGE_ACCESS_TOKEN = os.environ.get("CHOWCHOW_PAGE_ACCESS_TOKEN", "")
GEMINI_API_KEY    = os.environ.get("GEMINI_API_KEY", "") or os.environ.get("GOOGLE_API_KEY", "")

if not PAGE_ACCESS_TOKEN or not GEMINI_API_KEY:
    try:
        from config import PAGE_ACCESS_TOKEN as _tok, GOOGLE_API_KEY as _key
        if not PAGE_ACCESS_TOKEN:
            PAGE_ACCESS_TOKEN = _tok
        if not GEMINI_API_KEY:
            GEMINI_API_KEY = _key
    except ImportError:
        pass

if not GEMINI_API_KEY:
    GEMINI_API_KEY = "DUMMY_KEY"

client       = genai.Client(api_key=GEMINI_API_KEY, http_options=HttpOptions(timeout=300000))
TEXT_MODELS  = ["gemini-flash-latest", "gemini-flash-latest"]
OUTPUT_DIR   = "output"
FONT_PATH    = os.path.join(os.path.dirname(__file__), "fonts", "Sarabun-ExtraBold.ttf")
HISTORY_FILE = "dilemma_history.txt"
HEADERS      = {"User-Agent": "Mozilla/5.0 (compatible; ChowChowBot/1.0; +github)"}

ACCENT_COLOR = (255, 215, 0)   # เหลืองทอง #FFD700
WHITE_COLOR  = (255, 255, 255)

os.makedirs(OUTPUT_DIR, exist_ok=True)

DOG_SUBREDDITS = [
    "chowchow",
    "dogs",
    "rarepuppers",
    "WhatsWrongWithYourDog",
    "AnimalsBeingDerps",
    "AITA",
]

FIRST_PERSON_TERMS = ("ผม", "ฉัน", "ดิฉัน", "หนู", "เรา", "พวกเรา", "ตัวเรา", "ของเรา")

def contains_first_person(text):
    clean = (text or "").replace("\u200b", "")
    return any(term in clean for term in FIRST_PERSON_TERMS)

def apply_slang_rules(text):
    """Kept for callers; slang substitution was removed (content_quality.py)."""
    return text

def contains_thai(text):
    if not text:
        return False
    return any('\u0e00' <= char <= '\u0e7f' for char in text)

# ── History ──────────────────────────────────────────────────────────────────
def load_history():
    if os.path.exists(HISTORY_FILE):
        try:
            with open(HISTORY_FILE, "r", encoding="utf-8") as f:
                return [l.strip() for l in f if l.strip()]
        except Exception:
            return []
    return []

def save_to_history(url_or_key):
    items = load_history()
    items.append(url_or_key)
    items = items[-300:]
    try:
        with open(HISTORY_FILE, "w", encoding="utf-8") as f:
            for it in items:
                f.write(it + "\n")
    except Exception as e:
        print(f"History save error: {e}")

def reddit_title_key(title):
    norm = re.sub(r"[^\w฀-๿]+", "", (title or "").strip().lower())
    if not norm:
        return ""
    return "title:" + hashlib.md5(norm.encode("utf-8")).hexdigest()[:16]

# ── Reddit fetch ─────────────────────────────────────────────────────────────
def get_reddit_dog_story(history_set):
    NS = {"atom": "http://www.w3.org/2005/Atom"}
    subs = random.sample(DOG_SUBREDDITS, len(DOG_SUBREDDITS))
    for sub in subs:
        rss_url = f"https://www.reddit.com/r/{sub}/hot.rss?limit=30"
        try:
            resp = requests.get(rss_url, headers=HEADERS, timeout=10)
            resp.raise_for_status()
            root    = ET.fromstring(resp.content)
            entries = root.findall("atom:entry", NS)
            candidates = []
            for entry in entries:
                title   = entry.findtext("atom:title", "", NS).strip()
                content = entry.findtext("atom:content", "", NS)
                link_el = entry.find("atom:link", NS)
                permalink = link_el.get("href", "") if link_el is not None else ""

                body = re.sub(r"<[^>]+>", " ", content or "").strip()
                body = re.sub(r"\s{2,}", " ", body)

                if (len(body) >= 150
                        and permalink not in history_set
                        and reddit_title_key(title) not in history_set
                        and "reddit.com/r/" in permalink):
                    candidates.append({
                        "subreddit": sub,
                        "title":     title,
                        "body":      body[:1200],
                        "permalink": permalink,
                    })
            if candidates:
                chosen = random.choice(candidates[:15])
                print(f"Dog Story: r/{sub} | {chosen['title'][:70]}")
                return chosen
        except Exception as e:
            print(f"Reddit error ({sub}): {e}")
    return None

# ── Gemini text helper ───────────────────────────────────────────────────────
def gemini_text(prompt):
    for model in TEXT_MODELS:
        for attempt in range(2):
            try:
                resp = client.models.generate_content(model=model, contents=prompt)
                return resp.text.strip()
            except Exception as e:
                print(f"[{model}] attempt {attempt+1} failed: {e}")
                time.sleep(2)
    return ""

# ── Translation & Copywriting ────────────────────────────────────────────────
def generate_dog_dilemma(title="", body="", subreddit="dogs"):
    PERSONA = "คุณคือแอดมินเพจ 'Chow Chow' เพจคนเลี้ยงหมา น้ำเสียงอบอุ่น อารมณ์ดี เป็นกันเอง ลงท้าย 'ฮะ' เรียกผู้ติดตามว่า 'พี่ๆ'"
    PAGE = 'chowchow'
    ANGLES = ['พฤติกรรมน้องหมาในบ้านที่เจ้าของต้องเลือกวิธีรับมือ', 'การตัดสินใจของเจ้าของหมาที่มีทั้งข้อดีและข้อเสีย', 'เคล็ดลับดูแลน้องหมาที่ใช้ได้จริงจากเรื่องนี้']
    EXAMPLE1, EXAMPLE2 = 'หมาแย่งที่นอนเจ้าของ', 'ให้นอนด้วยหรือแยก?'
    FALLBACKS = [('หมาขนร่วงเต็มโซฟา', 'ดูดฝุ่นหรือแปรงขน?', 'ขนน้องหมาร่วงติดโซฟาทุกวัน จนเจ้าของต้องเดินดูดฝุ่นวันละหลายรอบฮะ\n\nบางบ้านเลือกดูดฝุ่นบ่อยๆ ส่วนบางบ้านบอกว่าแปรงขนน้องวันละ 5 นาทีช่วยได้มากกว่า เพราะเก็บขนก่อนร่วง\n\nบ้านพี่ๆ ใช้วิธีไหน ได้ผลกว่ากันฮะ? 1/2', 'ผมเลือกแปรงขนฮะ เก็บขนที่ต้นทางก่อนมันปลิว แล้วค่อยดูดฝุ่นวันละรอบก็พอ 2/2'), ('หมาแย่งเตียง 6 ฟุต', 'อุ้มลงหรือยอมนอนพื้น?', 'ถ้าซื้อเตียงใหญ่มา แต่น้องหมานอนกางขากลางเตียงจนคนแทบไม่มีที่ จะทำยังไงดีฮะ\n\nจะอุ้มน้องไปนอนเบาะของตัวเองก็กลัวน้องงอน จะปล่อยไว้ก็นอนไม่สบาย\n\nถ้าเป็นพี่ๆ จะฝึกให้น้องนอนที่ของตัวเอง หรือยอมแบ่งเตียงฮะ? 1/2', 'ผมว่าฝึกให้มีที่นอนของตัวเองดีกว่าฮะ วางเบาะไว้ข้างเตียง ให้ขนมตอนน้องไปนอนตรงนั้น 2/2'), ('หมาแทะโซฟาตอนอยู่บ้าน', 'ดุหรือหาของให้แทะ?', 'ถ้ากลับบ้านมาเจอโซฟาโดนแทะ แต่น้องทำหน้าสำนึกผิดจนดุไม่ลง จะทำยังไงดีฮะ\n\nบางคนว่าต้องดุทันทีให้จำ บางคนว่าน้องแทะเพราะเบื่อ ควรหาของให้แทะแทน\n\nพี่ๆ อยู่ทีมไหนฮะ? 1/2', 'ผมอยู่ทีมหาของให้แทะฮะ ดุย้อนหลังน้องไม่เข้าใจ เตรียมของเล่นขัดฟันไว้ก่อนออกจากบ้านช่วยได้เยอะ 2/2')]

    import content_quality as cq
    prompt = (
        f"{PERSONA}\n"
        "สรุปเรื่องจริงจาก Reddit ต่อไปนี้เป็นโพสต์ชวนคุย โดยเล่าตามต้นฉบับเท่านั้น:\n\n"
        f"Title: {title}\n"
        f"Body: {body}\n\n"
        f"มุมที่เน้น: {random.choice(ANGLES)}\n\n"
        f"{cq.story_rules(PAGE, 550)}"
        "9. เล่าแบบบุคคลที่สาม ห้ามอ้างว่าเป็นเรื่องของแอดมิน\n\n"
        "ตอบเป็น JSON เท่านั้น:\n"
        "{\n"
        f'  "image_line1": "พาดหัวบรรทัด 1 ยาว 8-14 ตัวอักษร บอกเรื่องชัด เช่น {EXAMPLE1}",\n'
        f'  "image_line2": "พาดหัวบรรทัด 2 ยาว 8-14 ตัวอักษร เป็นคำถามเลือกทาง เช่น {EXAMPLE2}",\n'
        '  "caption": "โพสต์ตามกฎข้างบน ลงท้ายด้วย 1/2",\n'
        '  "seed_comment": "ความเห็นแอดมิน 1-2 ประโยค เลือกข้างอย่างมีเหตุผล และให้ทิปที่ทำได้จริง ไม่แนะนำยาหรือวิธีรักษา ลงท้ายด้วย 2/2"\n'
        "}"
    )
    line1 = line2 = caption = seed_comment = ""
    feedback = ""
    # Without a real source the model would invent a "true story"; use presets instead.
    has_source = bool(str(title).strip() and str(body).strip())
    for _attempt in range(2 if has_source else 0):
        raw = gemini_text(prompt + feedback)
        m = re.search(r"\{.*\}", raw or "", re.DOTALL)
        if not m:
            continue
        try:
            data = json.loads(m.group())
        except Exception as e:
            print(f"JSON parse error: {e}")
            continue
        cand = [str(data.get(k, "")).strip() for k in ("image_line1", "image_line2", "caption", "seed_comment")]
        issues = cq.find_issues(cand[2], "story", 620) + [i for i in cq.find_issues(cand[3], "story", 400) if not i.startswith("stale_opener")]
        issues += [f"headline:{w}" for w in cq.BANNED_SLANG if w in cand[0] + cand[1]]
        if all(cand) and contains_thai(cand[0]) and contains_thai(cand[2]) and not issues:
            line1, line2, caption, seed_comment = cand
            break
        print(f"Story rejected: {issues or 'missing fields'}")
        feedback = "\n\nร่างก่อนหน้าผิดกฎ: " + ", ".join(issues or ["ข้อมูลไม่ครบ"]) + " เขียนใหม่ให้ผ่านทุกข้อ"

    if not caption:
        print("Using local dilemma fallbacks.")
        line1, line2, caption, seed_comment = random.choice(FALLBACKS)

    if "1/2" not in caption:
        caption = caption.rstrip() + " 1/2"
    if "2/2" not in seed_comment:
        seed_comment = seed_comment.rstrip() + " 2/2"
    return line1, line2, caption, seed_comment

# ── Text wrap helper ─────────────────────────────────────────────────────────
_LEADING_VOWELS  = set("เแโใไ")
_COMBINING_CHARS = set("่้๊๋์ิีึืุูัํ็")

def wrap_text(draw, text, font, max_width):
    words = [w for w in text.split(" ") if w]
    if not words:
        words = list(text)
    lines, cur = [], ""
    for w in words:
        test = (cur + " " + w).strip() if cur else w
        if draw.textbbox((0, 0), test, font=font)[2] <= max_width:
            cur = test
        else:
            if cur:
                lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    return lines or [text]

# ── Generate image ───────────────────────────────────────────────────────────
def generate_image(line1, line2):
    """Dark card 1080x1080 — line 1 เหลืองทอง (#FFD700), line 2 ขาว (#FFFFFF) auto-fit กึ่งกลาง"""
    bkk  = timezone(timedelta(hours=7))
    ts   = datetime.now(bkk).strftime("%Y%m%d_%H%M%S")
    path = os.path.join(OUTPUT_DIR, f"chowchow_dilemma_{ts}.jpg")

    W = H = 1080
    img  = Image.new("RGB", (W, H), (0, 0, 0))   # pure black
    draw = ImageDraw.Draw(img)

    PAD      = 80
    max_w    = W - PAD * 2   # 920px
    LINE_GAP = 28

    raw_lines = [l.strip() for l in [line1, line2] if l.strip()]

    font_size = 110
    best_font = None
    best_lines = []
    while font_size >= 36:
        font = ImageFont.truetype(FONT_PATH, font_size)
        wrapped = []
        for idx, l in enumerate(raw_lines):
            for w in wrap_text(draw, l, font, max_w):
                wrapped.append((w, idx == 0))

        def lh(text):
            bb = draw.textbbox((0, 0), text, font=font)
            return bb[3] - bb[1]

        total_h  = sum(lh(t) + LINE_GAP for t, _ in wrapped)
        width_ok = all(draw.textbbox((0, 0), t, font=font)[2] <= max_w for t, _ in wrapped)

        if total_h <= H - PAD * 2 and width_ok:
            best_font  = font
            best_lines = wrapped
            break
        font_size -= 4

    if not best_font:
        best_font  = ImageFont.truetype(FONT_PATH, 36)
        best_lines = []
        for idx, l in enumerate(raw_lines):
            for w in wrap_text(draw, l, best_font, max_w):
                best_lines.append((w, idx == 0))

    print(f"Chow Chow dilemma font size: {font_size} | lines: {len(best_lines)}")

    def lh(text):
        bb = draw.textbbox((0, 0), text, font=best_font)
        return bb[3] - bb[1]
    total_h = sum(lh(t) + LINE_GAP for t, _ in best_lines)

    y = (H - total_h) // 2

    for text, is_first in best_lines:
        bb = draw.textbbox((0, 0), text, font=best_font)
        w  = bb[2] - bb[0]
        x  = (W - w) // 2
        dy = y - bb[1]
        line_color = ACCENT_COLOR if is_first else WHITE_COLOR
        draw.text((x + 3, dy + 3), text, font=best_font, fill=(30, 30, 30))
        draw.text((x, dy), text, font=best_font, fill=line_color)
        y += lh(text) + LINE_GAP

    # watermark
    try:
        wm_font = ImageFont.truetype(FONT_PATH, 26)
        wm_text = "Chow Chow คนรักหมา"
        bb = draw.textbbox((0, 0), wm_text, font=wm_font)
        draw.text(((W - (bb[2]-bb[0])) // 2, H - 55), wm_text, font=wm_font, fill=(70, 70, 70))
    except Exception:
        pass

    img.save(path, "JPEG", quality=92)
    print(f"Chow Chow image saved: {path}")
    return path

# ── Facebook Posting ─────────────────────────────────────────────────────────
def post_seed_comment(post_id, seed_comment):
    if not seed_comment:
        return
    try:
        data = {"access_token": PAGE_ACCESS_TOKEN, "message": seed_comment}
        resp = requests.post(f"https://graph.facebook.com/v25.0/{post_id}/comments", data=data, timeout=60)
        res = resp.json()
        print(f"Admin Seed Comment: {'OK id=' + res.get('id', '') if 'id' in res else res}")
    except Exception as e:
        print(f"Error posting admin seed comment: {e}")

def post_facebook(img_path, caption, seed_comment=None):
    print("Posting dog dilemma to Facebook...")
    try:
        # Step 1: Upload photo as unpublished
        with open(img_path, "rb") as f:
            resp = requests.post(
                f"https://graph.facebook.com/v25.0/{PAGE_ID}/photos",
                data={"access_token": PAGE_ACCESS_TOKEN, "published": "false"},
                files={"source": ("dilemma.jpg", f, "image/jpeg")},
                timeout=60,
            )
        upload_result = resp.json()
        if "id" not in upload_result:
            print(f"Photo upload failed: {upload_result}")
            return None
        
        photo_id = upload_result["id"]
        print(f"Photo uploaded unpublished! ID: {photo_id}")
        
        # Step 2: Publish to feed
        resp2 = requests.post(
            f"https://graph.facebook.com/v25.0/{PAGE_ID}/feed",
            data={
                "access_token": PAGE_ACCESS_TOKEN,
                "message": caption,
                "attached_media": json.dumps([{"media_fbid": photo_id}])
            },
            timeout=60,
        )
        feed_result = resp2.json()
        if "id" in feed_result:
            post_id = feed_result["id"]
            print(f"Posted to feed! ID: {post_id}")
            # Step 3: Admin seed comment immediately (2/2)
            if seed_comment:
                post_seed_comment(post_id, seed_comment)
            add_affiliate_comments(post_id, caption)
            return post_id
        else:
            print(f"Feed publishing failed: {feed_result}")
            return None
    except Exception as e:
        print(f"Error posting to FB: {e}")
        return None

def add_affiliate_comments(post_id, caption):
    try:
        from affiliate_utils import get_all_comments
        comments = get_all_comments(caption=caption)
    except Exception:
        return
    delay = random.uniform(60, 180)
    print(f"Waiting {delay:.0f}s before first affiliate comment...")
    time.sleep(delay)
    for i, msg in enumerate(comments[:2], 1):
        if isinstance(msg, dict):
            data = {"access_token": PAGE_ACCESS_TOKEN, "message": msg["message"]}
            pic  = msg.get("picture_url", "")
            if pic and pic.startswith("http"):
                data["attachment_url"] = pic
        else:
            data = {"access_token": PAGE_ACCESS_TOKEN, "message": str(msg)}
        if not data.get("message", "").strip():
            continue
        r = requests.post(
            f"https://graph.facebook.com/v25.0/{post_id}/comments",
            data=data, timeout=60,
        )
        res = r.json()
        print(f"Affiliate Comment {i}: {'OK id=' + res['id'] if 'id' in res else res}")
        if i < len(comments):
            time.sleep(random.uniform(30, 90))

# ── Main ─────────────────────────────────────────────────────────────────────
def main(dry_run=False):
    history_set = set(load_history())
    post = get_reddit_dog_story(history_set)
    title = post["title"] if post else ""
    body = post["body"] if post else ""
    sub = post["subreddit"] if post else "dogs"

    line1, line2, caption, seed_comment = generate_dog_dilemma(title, body, sub)

    print("\n--- [CHOW CHOW DOG DILEMMA] ---")
    print(f"Line 1 (Gold):  {line1}")
    print(f"Line 2 (White): {line2}")
    print(f"Caption (1/2):\n{caption}\n")
    print(f"Seed Comment (2/2):\n{seed_comment}\n")

    img_path = generate_image(line1, line2)

    if dry_run:
        sample_path = os.path.join(OUTPUT_DIR, "chowchow_dilemma_sample.jpg")
        import shutil
        shutil.copy(img_path, sample_path)
        print(f"[DRY RUN] Generated sample card saved to: {sample_path}")
        print("[DRY RUN] Posting skipped.")
        return

    full_caption = f"{caption}\n\n#คนรักหมา #ทาสหมา #ChowChow"
    post_facebook(img_path, full_caption, seed_comment=seed_comment)

    if post:
        save_to_history(post["permalink"])
        save_to_history(reddit_title_key(post["title"]))

    try:
        if os.path.exists(img_path):
            os.unlink(img_path)
    except Exception:
        pass

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    main(dry_run=args.dry_run)
