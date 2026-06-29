# راه‌اندازی امن `ytig.alecasgari.com`

دامنه روی Cloudflare است. هدف: فقط **UI** عمومی باشد؛ **`/download` برای n8n از اینترنت بسته** بماند.

---

## معماری پیشنهادی

```
مرورگر → Cloudflare (HTTPS) → VPS :443 → Caddy → 127.0.0.1:9876
n8n (Docker) ──────────────────────────────→ giv-ytdlp:9876/download (شبکه داخلی)
```

---

## گزینه ۱ — Caddy روی VPS (پیشنهادی)

### DNS (Cloudflare)

| Type | Name | Content | Proxy |
|------|------|---------|-------|
| A | ytig | IP سرور `109.123.247.169` | Proxied (ابر نارنجی) |

### Caddy

فایل `/etc/caddy/Caddyfile` یا snippet:

```
ytig.alecasgari.com {
	encode gzip

	@blocked path /download
	handle @blocked {
		respond "Forbidden" 403
	}

	handle /api/* {
		reverse_proxy 127.0.0.1:9876
	}
	handle /static/* {
		reverse_proxy 127.0.0.1:9876
	}
	handle {
		reverse_proxy 127.0.0.1:9876
	}
}
```

```bash
sudo systemctl reload caddy
```

### SSL

- با Cloudflare Proxied: گزینه **Full (strict)** در SSL/TLS
- روی origin: Caddy خودش Let's Encrypt می‌گیرد **یا** Cloudflare Origin Certificate

### امنیت لایه اپ

- `GIV_YTDLP_UI_PASSWORD` در `.env` — **الزامی**
- `/download` از Caddy block — n8n فقط از `giv-ytdlp-net`

---

## گزینه ۲ — Cloudflare Tunnel (بدون باز کردن پورت 443)

اگر نمی‌خواهی پورت وب روی VPS باز باشد:

1. `cloudflared` روی سرور
2. Tunnel به `http://127.0.0.1:9876`
3. Public hostname: `ytig.alecasgari.com`
4. Cloudflare Access policy (ایمیل خودت) — لایه اضافه قبل از UI

---

## گزینه ۳ — Cloudflare Access (Zero Trust)

روی همان دامنه:

- Policy: فقط ایمیل `you@example.com` یا OTP
- حتی با رمز UI، یک لایه SSO اضافه می‌شود

رایگان برای تعداد محدود کاربر.

---

## چک‌لیست امنیت

- [ ] `/download` از اینترنت 403
- [ ] `GIV_YTDLP_UI_PASSWORD` قوی
- [ ] `GIV_YTDLP_TOKEN` خالی (n8n داخلی)
- [ ] cookies و `.env` هرگز در Git
- [ ] Cloudflare: Bot Fight Mode / Rate limiting روی `ytig` (اختیاری)
- [ ] فقط متد GET/POST لازم — بقیه deny

---

## تست بعد از بالا آمدن

```bash
curl -I https://ytig.alecasgari.com/
curl -I https://ytig.alecasgari.com/download   # باید 403
```

از مرورگر: ورود با رمز UI → لینک تست → R2.
