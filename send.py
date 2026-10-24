import os, json, random, sys
import requests

REST_KEY = os.environ["KAKAO_REST_API_KEY"]
CLIENT_SECRET = os.environ.get("KAKAO_CLIENT_SECRET", "")
ITEMS_DIR = "items"
STATE_DIR = "state"
SENT_FILE = os.path.join(STATE_DIR, "sent.json")
TOKEN_FILE = os.path.join(STATE_DIR, "refresh_token.txt")
LINK = "https://developers.kakao.com"
IMG_EXTS = [".jpg", ".jpeg", ".png", ".JPG", ".JPEG", ".PNG"]

os.makedirs(STATE_DIR, exist_ok=True)


def get_access_token():
    refresh = os.environ.get("KAKAO_REFRESH_TOKEN", "")
    if os.path.exists(TOKEN_FILE):
        saved = open(TOKEN_FILE, encoding="utf-8").read().strip()
        if saved:
            refresh = saved
    data = {
        "grant_type": "refresh_token",
        "client_id": REST_KEY,
        "refresh_token": refresh,
    }
    if CLIENT_SECRET:
        data["client_secret"] = CLIENT_SECRET
    r = requests.post("https://kauth.kakao.com/oauth/token", data=data)
    j = r.json()
    if "access_token" not in j:
        print("토큰 갱신 실패:", j.get("error"), j.get("error_description"))
        sys.exit(1)
    if j.get("refresh_token"):
        with open(TOKEN_FILE, "w", encoding="utf-8") as f:
            f.write(j["refresh_token"])
        print("리프레시 토큰이 새로 갱신되었습니다.")
    return j["access_token"]


def load_items():
    default_title = "오늘의 산업보안·안전 알림"
    items = {}
    if not os.path.isdir(ITEMS_DIR):
        return items
    stems = set()
    for name in os.listdir(ITEMS_DIR):
        if name.startswith("_"):
            continue
        base, ext = os.path.splitext(name)
        if ext == ".txt" or ext in IMG_EXTS:
            stems.add(base)
    for stem in sorted(stems):
        title, body, image = default_title, "", None
        txt = os.path.join(ITEMS_DIR, stem + ".txt")
        has_text = False
        if os.path.exists(txt):
            text = open(txt, encoding="utf-8").read().strip()
            if text:
                lines = text.splitlines()
                title = lines[0].strip()
                body = "\n".join(lines[1:]).strip()
                has_text = True
        for ext in IMG_EXTS:
            p = os.path.join(ITEMS_DIR, stem + ext)
            if os.path.exists(p):
                image = p
                break
        if not image and not has_text:
            continue
        items[stem] = {"title": title, "body": body, "image": image}
    return items


def pick(items):
    sent = []
    if os.path.exists(SENT_FILE):
        sent = json.load(open(SENT_FILE, encoding="utf-8"))
    sent = [s for s in sent if s in items]
    pool = [k for k in items if k not in sent]
    if not pool:
        sent = []
        pool = list(items)
    chosen = random.choice(pool)
    return chosen, sent


def upload_image(token, path):
    with open(path, "rb") as f:
        r = requests.post(
            "https://kapi.kakao.com/v2/api/talk/message/image/upload",
            headers={"Authorization": f"Bearer {token}"},
            files={"file": (os.path.basename(path), f)},
        )
    j = r.json()
    try:
        o = j["infos"]["original"]
        return o["url"], o["width"], o["height"]
    except Exception:
        print("이미지 업로드 실패:", j)
        sys.exit(1)


def send(token, item):
    title, body = item["title"], item["body"]
    link = {"web_url": LINK, "mobile_web_url": LINK}
    if item["image"]:
        url, w, h = upload_image(token, item["image"])
        link = {"web_url": url, "mobile_web_url": url}
        tpl = {
            "object_type": "feed",
            "content": {
                "title": title[:50],
                "description": body[:200],
                "image_url": url,
                "image_width": w,
                "image_height": h,
                "link": link,
            },
        }
    else:
        text = (title + "\n\n" + body).strip()
        tpl = {"object_type": "text", "text": text[:200], "link": link}
    r = requests.post(
        "https://kapi.kakao.com/v2/api/talk/memo/default/send",
        headers={"Authorization": f"Bearer {token}"},
        data={"template_object": json.dumps(tpl, ensure_ascii=False)},
    )
    j = r.json()
    if j.get("result_code") != 0:
        print("전송 실패:", j)
        sys.exit(1)


def main():
    items = load_items()
    if not items:
        print("items 폴더에 .txt 자료가 없습니다.")
        sys.exit(1)
    token = get_access_token()
    chosen, sent = pick(items)
    send(token, items[chosen])
    sent.append(chosen)
    with open(SENT_FILE, "w", encoding="utf-8") as f:
        json.dump(sent, f, ensure_ascii=False)
    print("발송 완료:", chosen)


main()
