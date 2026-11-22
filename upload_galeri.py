import os, re, json, time, base64, requests
from io import BytesIO
from PIL import Image

BOT_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
ADMIN_ID = str(os.environ["TELEGRAM_ADMIN_ID"])
GITHUB_TOKEN = os.environ["GITHUB_TOKEN"]
REPO = os.environ["GITHUB_REPOSITORY"]
PAYLOAD = json.loads(os.environ["TG_PAYLOAD"])

msg = PAYLOAD.get("message", {})
chat_id = str(msg.get("chat", {}).get("id", ""))
user_id = str(msg.get("from", {}).get("id", ""))
photos = msg.get("photo", [])
caption = msg.get("caption", "")

def send_tg(text):
    requests.post(f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage", json={"chat_id": chat_id, "text": text, "parse_mode": "Markdown"})

if user_id != ADMIN_ID or not photos:
    exit(0)

parts = [p.strip() for p in caption.split("|")]
if len(parts) < 3 or parts[0].lower() not in ["wisata", "jalan", "trademark"]:
    send_tg("⚠️ Format salah! Gunakan:\n`wisata | Judul Foto | Deskripsi singkat`")
    exit(0)

kategori, judul, deskripsi = parts[0].lower(), parts[1], parts[2]

# 1. Ambil file dari Telegram
file_id = photos[-1]["file_id"]
file_path = requests.get(f"https://api.telegram.org/bot{BOT_TOKEN}/getFile?file_id={file_id}").json()["result"]["file_path"]
img_bytes = requests.get(f"https://api.telegram.org/file/bot{BOT_TOKEN}/{file_path}").content

# 2. Kompres ke WebP
img = Image.open(BytesIO(img_bytes)).convert("RGB")
if img.width > 1280:
    img = img.resize((1280, int(img.height * (1280 / img.width))), Image.Resampling.LANCZOS)
buf = BytesIO()
img.save(buf, format="WEBP", quality=82)

slug = re.sub(r'[\s-]+', '-', re.sub(r'[^a-z0-9\s-]', '', judul.lower().strip()))
filename = f"galeri/{slug}-{int(time.time())}.webp"

headers = {"Authorization": f"token {GITHUB_TOKEN}", "Accept": "application/vnd.github.v3+json"}

def gh_put(path, raw_bytes, commit_msg):
    url = f"https://api.github.com/repos/{REPO}/contents/{path}"
    r = requests.get(url, headers=headers)
    sha = r.json().get("sha") if r.status_code == 200 else None
    data = {"message": commit_msg, "content": base64.b64encode(raw_bytes).decode()}
    if sha: data["sha"] = sha
    return requests.put(url, headers=headers, json=data).status_code in [200, 201]

if gh_put(filename, buf.getvalue(), f"Upload galeri: {judul}"):
    r_json = requests.get(f"https://api.github.com/repos/{REPO}/contents/galeri.json", headers=headers)
    galeri = json.loads(base64.b64decode(r_json.json()["content"]).decode()) if r_json.status_code == 200 else []
    galeri.insert(0, {
        "category": kategori,
        "title": judul,
        "desc": deskripsi,
        "src": f"https://cdn.jsdelivr.net/gh/{REPO}@main/{filename}"
    })
    gh_put("galeri.json", json.dumps(galeri, indent=2, ensure_ascii=False).encode(), f"Update galeri.json: {judul}")
    send_tg(f"✅ *Berhasil tayang di Galeri!*\n📂 Kategori: `{kategori}`\n🖼️ Judul: {judul}")
