# youtube-instagram-downloader

سرویس خودمیزبان برای **دانلود ویدیو از یوتیوب و اینستاگرام** با [yt-dlp](https://github.com/yt-dlp/yt-dlp)، آپلود خودکار به **Cloudflare R2**، و یک **رابط وب ساده با رمز**.

این پروژه جدا از [givsharifi-website](https://github.com/alecasgari/givsharifi-website) نگهداری می‌شود؛ روی VPS به‌صورت Docker اجرا می‌شود و از طریق شبکه داخلی Docker به **n8n** وصل می‌شود.

---

## فهرست

- [چه کاری می‌کند](#چه-کاری-می‌کند)
- [تکنولوژی](#تکنولوژی)
- [معماری](#معماری)
- [API](#api)
- [رابط وب (UI)](#رابط-وب-ui)
- [نصب روی سرور](#نصب-روی-سرور)
- [اتصال به n8n](#اتصال-به-n8n)
- [cookies یوتیوب](#cookies-یوتیوب)
- [دسترسی عمومی با HTTPS](#دسترسی-عمومی-با-https)
- [به‌روزرسانی](#به‌روزرسانی)
- [عیب‌یابی](#عیب‌یابی)
- [امنیت](#امنیت)

---

## چه کاری می‌کند

1. لینک یوتیوب یا ریل اینستاگرام می‌گیرد
2. با yt-dlp ویدیو MP4 + پوستر JPG دانلود می‌کند
3. در صورت نیاز هر دو را به bucket R2 (مثلاً `library/VIDEO_ID.mp4`) آپلود می‌کند
4. متادیتا (عنوان، مدت، تاریخ و…) را به‌صورت JSON برمی‌گرداند

**مصرف‌کننده‌ها:**

| مصرف‌کننده | مسیر |
|------------|------|
| **n8n** (ربات تلگرام → انتشار ویدیو) | `POST /download` از شبکه Docker داخلی |
| **شما (مرورگر)** | صفحه وب `/` با رمز → `POST /api/ui-download` |

---

## تکنولوژی

| لایه | ابزار |
|------|--------|
| زبان | Python 3.12 |
| دانلود | yt-dlp + ffmpeg |
| یوتیوب ۲۰۲۶+ | Deno + remote-components EJS |
| ذخیره ابری | Cloudflare R2 (S3-compatible via boto3) |
| اجرا | Docker + docker compose |
| HTTP | stdlib `http.server` (سبک، بدون فریم‌ورک سنگین) |
| UI | HTML / CSS / JavaScript استاتیک |
| اتوماسیون | n8n روی همان VPS |

---

## معماری

```
┌─────────────┐     Docker network giv-ytdlp-net      ┌──────────────────┐
│   n8n-app   │ ─── POST /download (بدون token) ────► │  giv-ytdlp:9876  │
└─────────────┘                                       │  (این سرویس)     │
                                                      └────────┬─────────┘
┌─────────────┐     localhost:9876 + Caddy HTTPS                 │
│  مرورگر تو  │ ─── / و /api/ui-download (با رمز) ──────────────┘
└─────────────┘
                                                      │
                                                      ▼
                                            Cloudflare R2 (library/)
```

- نام کانتینر: **`giv-ytdlp`** (عمداً ثابت مانده تا n8n نشکند)
- شبکه: **`giv-ytdlp-net`**
- پورت روی host: فقط **`127.0.0.1:9876`** (نه اینترنت خام)

---

## API

### `GET /health`

وضعیت سرویس، R2، UI.

### `POST /download` — مسیر n8n

```json
{
  "url": "https://www.youtube.com/watch?v=XXXX",
  "work_id": "n8n-execution-id",
  "token": "فقط اگر GIV_YTDLP_TOKEN ست شده",
  "upload_r2": true
}
```

پاسخ موفق (خلاصه):

```json
{
  "ok": true,
  "video_id": "abc123",
  "source": "youtube",
  "video_meta": { "title": "...", "duration_string": "3:01" },
  "r2": {
    "mp4_url": "https://media.givsharifi.com/library/abc123.mp4",
    "poster_url": "https://media.givsharifi.com/library/abc123.jpg"
  }
}
```

- فقط **یک دانلود هم‌زمان** — درخواست دوم: `503 another download is in progress`

### `POST /api/ui-download` — مسیر UI

همان بدنه `/download` به‌اضافه فیلد **`password`** (مقدار `GIV_YTDLP_UI_PASSWORD`).

---

## رابط وب (UI)

بعد از deploy و (در صورت نیاز) تنظیم Caddy:

1. باز کردن آدرس عمومی (مثلاً `https://download.example.com`)
2. وارد کردن رمز (`GIV_YTDLP_UI_PASSWORD`)
3. چسباندن لینک یوتیوب/اینستا
4. تیک «آپلود به R2» را روشن/خاموش کن
5. نتیجه JSON + لینک‌های R2 نمایش داده می‌شود

رمز فقط در `sessionStorage` مرورگر نگه داشته می‌شود (نه localStorage).

---

## نصب روی سرور

### پیش‌نیاز

- Docker + Docker Compose روی VPS
- کلیدهای R2 از Cloudflare
- (برای یوتیوب) فایل `cookies.txt` از مرورگر

### قدم ۱ — clone

```bash
mkdir -p /home/alecadmin/youtube-instagram-downloader
cd /home/alecadmin/youtube-instagram-downloader
git clone https://github.com/alecasgari/youtube-instagram-downloader.git .
```

اگر قبلاً `/home/alecadmin/giv-ytdlp` داشتی، می‌توانی همان فولدر را با clone جایگزین کنی یا مسیر جدید بسازی.

### قدم ۲ — `.env`

```bash
cp env.example .env
nano .env
```

حداقل پر کن:

```env
GIV_YTDLP_UI_PASSWORD=یک-رمز-قوی
R2_ACCOUNT_ID=...
R2_ACCESS_KEY_ID=...
R2_SECRET_ACCESS_KEY=...
R2_BUCKET=givsharifi-videos
R2_PREFIX=library
R2_PUBLIC_BASE_URL=https://media.givsharifi.com
```

`GIV_YTDLP_TOKEN` را **خالی** بگذار تا n8n بدون token کار کند.

یا با متغیرهای محیطی:

```bash
export R2_ACCOUNT_ID=... R2_ACCESS_KEY_ID=... R2_SECRET_ACCESS_KEY=...
bash setup-on-server.sh
```

### قدم ۳ — build و run

```bash
docker compose build
docker compose up -d
docker compose ps
```

### قدم ۴ — cookies یوتیوب

روی لپ‌تاپ: افزونه **Get cookies.txt LOCALLY** → export از youtube.com

```bash
docker cp cookies.txt giv-ytdlp:/data/cookies.txt
docker compose restart
```

### قدم ۵ — تست

```bash
bash verify-on-server.sh "https://youtu.be/SHORT_ID"
```

---

## اتصال به n8n

**فقط یک بار** (اگر قبلاً انجام نشده):

```bash
docker network connect giv-ytdlp-net n8n-app
```

تست از داخل n8n:

```bash
docker exec n8n-app wget -qO- http://giv-ytdlp:9876/health
```

ورکفلو n8n (`02-publish-video`) باید به این آدرس POST بزند:

```
http://giv-ytdlp:9876/download
```

بدنه:

```json
{ "url": "...", "work_id": "{{ $execution.id }}", "upload_r2": true }
```

**نیازی به تغییر ورکفلو n8n نیست** — نام کانتینر و API همان است.

---

## cookies یوتیوب

| پلتفرم | cookies |
|--------|---------|
| اینستاگرام | اغلب بدون cookies |
| یوتیوب روی VPS | تقریباً همیشه لازم |

مسیر داخل کانتینر: `/data/cookies.txt`

اگر منقضی شد: دوباره export و `docker cp`.

---

## دسترسی عمومی با HTTPS

پورت را مستقیم به `0.0.0.0` باز **نکن**.

1. سرویس روی `127.0.0.1:9876` است (در `docker-compose.yml`)
2. فایل `Caddyfile.example` را ببین
3. مسیر `/download` را از اینترنت **مسدود** کن (فقط UI و `/api/*`)
4. n8n همچنان از شبکه Docker به `/download` دسترسی دارد

---

## به‌روزرسانی

روی VPS:

```bash
cd /home/alecadmin/youtube-instagram-downloader
bash deploy.sh
```

یا دستی:

```bash
git pull
docker compose build
docker compose up -d --force-recreate
```

روی لپ‌تاپ: تغییر بده → `git push` → روی سرور `deploy.sh`.

---

## عیب‌یابی

| مشکل | راه‌حل |
|------|--------|
| n8n `ECONNREFUSED` | `docker network connect giv-ytdlp-net n8n-app` |
| یوتیوب bot / sign in | cookies تازه در `/data/cookies.txt` |
| `R2 not configured` | `.env` را چک کن؛ `docker compose up -d` |
| `503 another download` | صبر کن تا دانلود قبلی تمام شود |
| UI «رمز اشتباه» | `GIV_YTDLP_UI_PASSWORD` در `.env` |
| لاگ | `docker compose logs -f giv-ytdlp` |

---

## امنیت

- `cookies.txt` و `.env` را **commit نکن** (در `.gitignore` هستند)
- `GIV_YTDLP_UI_PASSWORD` برای مرورگر
- `GIV_YTDLP_TOKEN` اختیاری برای API — اگر ست کنی، n8n هم باید token بفرستد
- پیشنهاد: token خالی + `/download` فقط از Docker network + Caddy مسیر `/download` را از بیرون block کند

---

## ساختار پروژه

```
.
├── server.py          # HTTP API + UI
├── download.py        # yt-dlp
├── r2_upload.py       # آپلود R2
├── config.py
├── static/            # UI
├── docker-compose.yml
├── Dockerfile
├── deploy.sh
├── setup-on-server.sh
├── verify-on-server.sh
└── Caddyfile.example
```

---

## لایسنس

استفاده خصوصی — پروژه Giv Sharifi / alecasgari.
