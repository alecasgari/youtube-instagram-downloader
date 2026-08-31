(function () {
  const loginCard = document.getElementById("login-card");
  const app = document.getElementById("app");
  const usernameInput = document.getElementById("username");
  const passwordInput = document.getElementById("password");
  const loginBtn = document.getElementById("login-btn");
  const loginError = document.getElementById("login-error");
  const urlInput = document.getElementById("url");
  const uploadR2 = document.getElementById("upload-r2");
  const downloadBtn = document.getElementById("download-btn");
  const logoutBtn = document.getElementById("logout-btn");
  const statusEl = document.getElementById("status");
  const resultEl = document.getElementById("result");
  const cookieMeta = document.getElementById("cookie-meta");
  const youtubeCookies = document.getElementById("youtube-cookies");
  const instagramCookies = document.getElementById("instagram-cookies");
  const cookiesBtn = document.getElementById("cookies-btn");
  const cookieStatus = document.getElementById("cookie-status");

  function showLogin(message) {
    loginCard.hidden = false;
    app.hidden = true;
    if (message) {
      loginError.hidden = false;
      loginError.textContent = message;
    } else {
      loginError.hidden = true;
    }
  }

  function showApp() {
    loginCard.hidden = true;
    app.hidden = false;
    loginError.hidden = true;
    passwordInput.value = "";
  }

  function setStatus(el, text, kind) {
    el.textContent = text || "";
    el.className = "status" + (kind ? " " + kind : "");
  }

  function formatCookies(info) {
    if (!info || !info.present) return "هنوز کوکی روی سرور نیست.";
    const when = info.updated_at ? new Date(info.updated_at).toLocaleString("fa-IR") : "نامشخص";
    return `آخرین به‌روزرسانی: ${when} — یوتیوب ${info.youtube} کوکی، اینستاگرام ${info.instagram} کوکی.`;
  }

  async function readJson(res) {
    return res.json().catch(() => ({}));
  }

  async function refreshMe() {
    const res = await fetch("/api/ui-me", { credentials: "same-origin" });
    const data = await readJson(res);
    if (res.status === 401) {
      showLogin();
      return false;
    }
    if (!res.ok) {
      showLogin(data.error || "نشست نامعتبر است.");
      return false;
    }
    cookieMeta.textContent = formatCookies(data.cookies);
    showApp();
    return true;
  }

  loginBtn.addEventListener("click", async () => {
    const username = usernameInput.value.trim();
    const password = passwordInput.value;
    if (!username || !password) {
      showLogin("نام کاربری و رمز را وارد کنید.");
      loginCard.hidden = false;
      return;
    }
    loginBtn.disabled = true;
    loginError.hidden = true;
    try {
      const res = await fetch("/api/ui-login", {
        method: "POST",
        credentials: "same-origin",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ username, password }),
      });
      const data = await readJson(res);
      if (!res.ok) {
        showLogin(data.error || "ورود ناموفق.");
        return;
      }
      await refreshMe();
    } catch (err) {
      showLogin("اتصال به سرور برقرار نشد.");
    } finally {
      loginBtn.disabled = false;
    }
  });

  passwordInput.addEventListener("keydown", (e) => {
    if (e.key === "Enter") loginBtn.click();
  });
  usernameInput.addEventListener("keydown", (e) => {
    if (e.key === "Enter") passwordInput.focus();
  });

  logoutBtn.addEventListener("click", async () => {
    await fetch("/api/ui-logout", {
      method: "POST",
      credentials: "same-origin",
      headers: { "Content-Type": "application/json" },
      body: "{}",
    });
    showLogin();
  });

  downloadBtn.addEventListener("click", async () => {
    const url = urlInput.value.trim();
    if (!url) {
      setStatus(statusEl, "لینک ویدیو را وارد کنید.", "err");
      return;
    }
    downloadBtn.disabled = true;
    resultEl.hidden = true;
    setStatus(statusEl, "در حال دانلود… ممکن است چند دقیقه طول بکشد.", "busy");
    try {
      const res = await fetch("/api/ui-download", {
        method: "POST",
        credentials: "same-origin",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          url,
          work_id: "ui-" + Date.now(),
          upload_r2: uploadR2.checked,
        }),
      });
      const data = await readJson(res);
      if (res.status === 401) {
        showLogin("نشست تمام شد. دوباره وارد شوید.");
        return;
      }
      if (!data.ok) {
        setStatus(statusEl, data.error || "خطا در دانلود", "err");
        return;
      }
      setStatus(statusEl, "دانلود انجام شد.", "ok");
      const title = (data.video_meta && data.video_meta.title) || data.video_id;
      const mp4 = data.r2 && data.r2.mp4_url;
      const poster = data.r2 && data.r2.poster_url;
      resultEl.hidden = false;
      resultEl.innerHTML =
        `<p><strong>${escapeHtml(title)}</strong></p>` +
        `<p>منبع: ${escapeHtml(data.source || "")} · شناسه: ${escapeHtml(data.video_id || "")}</p>` +
        (mp4 ? `<p><a href="${escapeAttr(mp4)}" target="_blank" rel="noopener">فایل MP4</a></p>` : "") +
        (poster ? `<p><a href="${escapeAttr(poster)}" target="_blank" rel="noopener">پوستر</a></p>` : "");
    } catch (err) {
      setStatus(statusEl, "خطای شبکه یا timeout — دوباره تلاش کنید.", "err");
    } finally {
      downloadBtn.disabled = false;
    }
  });

  cookiesBtn.addEventListener("click", async () => {
    const youtube = youtubeCookies.value;
    const instagram = instagramCookies.value;
    if (!youtube.trim() && !instagram.trim()) {
      setStatus(cookieStatus, "حداقل یکی از دو کادر کوکی را پیست کنید.", "err");
      return;
    }
    cookiesBtn.disabled = true;
    setStatus(cookieStatus, "در حال اعمال روی سرور…", "busy");
    try {
      const res = await fetch("/api/ui-cookies", {
        method: "POST",
        credentials: "same-origin",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ youtube, instagram }),
      });
      const data = await readJson(res);
      if (res.status === 401) {
        showLogin("نشست تمام شد. دوباره وارد شوید.");
        return;
      }
      if (!data.ok) {
        setStatus(cookieStatus, data.error || "اعمال کوکی ناموفق بود.", "err");
        return;
      }
      cookieMeta.textContent = formatCookies(data.cookies);
      youtubeCookies.value = "";
      instagramCookies.value = "";
      setStatus(cookieStatus, "کوکی‌ها روی سرور اعمال شد. همان لینک را دوباره امتحان کنید.", "ok");
    } catch (err) {
      setStatus(cookieStatus, "خطای شبکه.", "err");
    } finally {
      cookiesBtn.disabled = false;
    }
  });

  function escapeHtml(str) {
    return String(str)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }

  function escapeAttr(str) {
    return escapeHtml(str).replace(/'/g, "&#39;");
  }

  refreshMe().catch(() => showLogin());
})();
