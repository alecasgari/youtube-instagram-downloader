(function () {
  const SESSION_KEY = "giv-ytdlp-ui-password";

  const loginCard = document.getElementById("login-card");
  const downloadCard = document.getElementById("download-card");
  const passwordInput = document.getElementById("password");
  const loginBtn = document.getElementById("login-btn");
  const loginError = document.getElementById("login-error");
  const urlInput = document.getElementById("url");
  const uploadR2 = document.getElementById("upload-r2");
  const downloadBtn = document.getElementById("download-btn");
  const logoutBtn = document.getElementById("logout-btn");
  const statusEl = document.getElementById("status");
  const resultEl = document.getElementById("result");

  function getPassword() {
    return sessionStorage.getItem(SESSION_KEY) || "";
  }

  function setPassword(value) {
    if (value) sessionStorage.setItem(SESSION_KEY, value);
    else sessionStorage.removeItem(SESSION_KEY);
  }

  function showDownloadView() {
    loginCard.hidden = true;
    downloadCard.hidden = false;
    loginError.hidden = true;
  }

  function showLoginView() {
    loginCard.hidden = false;
    downloadCard.hidden = true;
    passwordInput.value = "";
    setPassword("");
  }

  function setStatus(text, kind) {
    statusEl.textContent = text || "";
    statusEl.className = "status" + (kind ? " " + kind : "");
  }

  async function probePassword(password) {
    const res = await fetch("/api/ui-download", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ password, url: "", upload_r2: false }),
    });
    if (res.status === 401) return false;
    const data = await res.json().catch(() => ({}));
    if (res.status === 400 && data.error === "url required") return true;
    return res.ok || res.status === 400;
  }

  loginBtn.addEventListener("click", async () => {
    const password = passwordInput.value.trim();
    if (!password) {
      loginError.hidden = false;
      loginError.textContent = "رمز را وارد کن.";
      return;
    }
    loginBtn.disabled = true;
    loginError.hidden = true;
    try {
      const ok = await probePassword(password);
      if (!ok) {
        loginError.hidden = false;
        loginError.textContent = "رمز اشتباه است.";
        return;
      }
      setPassword(password);
      showDownloadView();
    } catch (err) {
      loginError.hidden = false;
      loginError.textContent = "اتصال به سرور برقرار نشد.";
    } finally {
      loginBtn.disabled = false;
    }
  });

  logoutBtn.addEventListener("click", showLoginView);

  downloadBtn.addEventListener("click", async () => {
    const password = getPassword();
    const url = urlInput.value.trim();
    if (!password) {
      showLoginView();
      return;
    }
    if (!url) {
      setStatus("لطفاً لینک ویدیو را وارد کن.", "err");
      return;
    }

    downloadBtn.disabled = true;
    resultEl.hidden = true;
    setStatus("در حال دانلود… ممکن است چند دقیقه طول بکشد.", "busy");

    try {
      const res = await fetch("/api/ui-download", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          password,
          url,
          work_id: "ui-" + Date.now(),
          upload_r2: uploadR2.checked,
        }),
      });
      const data = await res.json();
      if (res.status === 401) {
        showLoginView();
        return;
      }
      if (!data.ok) {
        setStatus(data.error || "خطا در دانلود", "err");
        return;
      }
      setStatus("انجام شد ✓", "ok");
      resultEl.hidden = false;
      resultEl.textContent = JSON.stringify(data, null, 2);
    } catch (err) {
      setStatus("خطای شبکه یا timeout — دوباره تلاش کن.", "err");
    } finally {
      downloadBtn.disabled = false;
    }
  });

  if (getPassword()) {
    showDownloadView();
  }
})();
