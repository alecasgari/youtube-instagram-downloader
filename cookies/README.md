# Cookies (secrets — never commit)

این پوشه فایل‌های حساس مرورگر را نگه می‌دارد. **هیچ‌کدام push نمی‌شوند.**

## فایل‌ها

| فایل | منبع |
|------|------|
| `youtube.export.txt` | Export از `youtube.com` با افزونه Get cookies.txt LOCALLY |
| `instagram.export.txt` | Export از `instagram.com` |
| `cookies.txt` | خروجی `python scripts/merge-cookies.py` — همین را به سرور می‌فرستی |

## روی لپ‌تاپ

```bash
cd youtube-instagram-downloader
python scripts/merge-cookies.py
```

## روی سرور

```bash
# یک بار از لپ‌تاپ (فقط cookies — کد از git pull می‌آید):
scp cookies/cookies.txt alecadmin@109.123.247.169:~/youtube-instagram-downloader/cookies/cookies.txt

# روی سرور:
cd ~/youtube-instagram-downloader
bash scripts/install-cookies.sh
```
