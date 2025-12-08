const API_BASE = "http://localhost:5000/api";

const form = document.getElementById("scrape-form");
const statusBox = document.getElementById("status");
const tbody = document.getElementById("articles-body");
const refreshBtn = document.getElementById("refresh");

function setStatus(msg, type = "info") {
  statusBox.textContent = msg;
  statusBox.className = `status ${type}`;
}

function renderArticles(list) {
  tbody.innerHTML = "";
  if (!list || list.length === 0) {
    tbody.innerHTML = `<tr><td colspan="11">Kayıt bulunamadı</td></tr>`;
    return;
  }
  list.forEach((item) => {
    const authorsRaw = item.yazarlar ?? item.author ?? item.yazar ?? [];
    let authors = [];
    if (Array.isArray(authorsRaw)) {
      authors = authorsRaw;
    } else if (typeof authorsRaw === "string") {
      authors = [authorsRaw];
    } else if (authorsRaw && typeof authorsRaw === "object") {
      authors = Object.values(authorsRaw);
    }
    const baslik = item.baslik || item.title || "-";
    const source = item.adres || item.source_url || "";
    const sourceLink = source ? `<a href="${source}" target="_blank">Link</a>` : "-";
    
    // Cilt/Sayı bilgisini birleştir
    let ciltSayi = "";
    if (item.cilt && item.sayı) {
      ciltSayi = `Cilt ${item.cilt}, Sayı ${item.sayı}`;
    } else if (item.cilt) {
      ciltSayi = `Cilt ${item.cilt}`;
    } else if (item.sayı) {
      ciltSayi = `Sayı ${item.sayı}`;
    }
    
    const tr = document.createElement("tr");
    tr.innerHTML = `
      <td>${baslik}</td>
      <td>${authors.join(", ") || "-"}</td>
      <td>${item.yil || "-"}</td>
      <td>${item.yayin_tarihi || item.yayın_tarihi || "-"}</td>
      <td>${item.dergi || item.konferans || "-"}</td>
      <td>${ciltSayi || "-"}</td>
      <td>${item.sayfalar || "-"}</td>
      <td>${item.yayinci || item.yayıncı || item.publisher || "-"}</td>
      <td>${item.atif_sayisi ?? "-"}</td>
      <td>${sourceLink}</td>
      <td>${item.pdf_url && item.pdf_url !== "PDF Yok" ? `<a href="${item.pdf_url}" target="_blank">PDF</a>` : "-"}</td>
    `;
    tbody.appendChild(tr);
  });
}

async function fetchArticles() {
  setStatus("Liste yükleniyor...", "info");
  try {
    const res = await fetch(`${API_BASE}/articles`);
    const data = await res.json();
    renderArticles(data);
    setStatus("Hazır", "success");
  } catch (err) {
    console.error(err);
    setStatus("Liste alınamadı", "error");
  }
}

form.addEventListener("submit", async (e) => {
  e.preventDefault();
  const author = document.getElementById("author").value.trim();
  if (!author) {
    setStatus("Yazar adı zorunlu", "error");
    return;
  }

  setStatus("Scrape ediliyor, lütfen bekleyin... (Bu işlem birkaç dakika sürebilir)", "info");
  try {
    // Timeout: 10 dakika (600000ms) - scraping uzun sürebilir
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), 600000);
    
    const res = await fetch(`${API_BASE}/scrape`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ author_name: author }),
      signal: controller.signal,
    });
    clearTimeout(timeoutId);
    
    const data = await res.json();
    if (res.ok) {
      if (data.inserted > 0) {
        setStatus(`Başarılı! ${data.inserted} makale kaydedildi`, "success");
        renderArticles(data.last || []);
      } else {
        setStatus(data.message || "Makale bulunamadı", "info");
        renderArticles(data.last || []);
      }
    } else {
      setStatus(data.error || data.message || "Bir şey ters gitti", "error");
      console.error("Scrape hatası:", data);
    }
  } catch (err) {
    console.error("Scrape hatası:", err);
    if (err.name === 'AbortError') {
      setStatus("İstek zaman aşımına uğradı. Lütfen tekrar deneyin.", "error");
    } else {
      setStatus(`Hata: ${err.message || "İstek gönderilemedi"}`, "error");
    }
  }
});

refreshBtn.addEventListener("click", fetchArticles);

// ilk yüklemede listeyi çek (otomatik)
document.addEventListener("DOMContentLoaded", fetchArticles);

