const form = document.getElementById("form");
const btn = document.getElementById("btn");
const ilerleme = document.getElementById("ilerleme");
const dolgu = document.getElementById("dolgu");
const ilerlemeMetin = document.getElementById("ilerleme-metin");
const sonuc = document.getElementById("sonuc");
const ozetMetin = document.getElementById("ozet-metin");
const belgeler = document.getElementById("belgeler");
const hata = document.getElementById("hata");

form.addEventListener("submit", async (e) => {
  e.preventDefault();
  hata.hidden = true; sonuc.hidden = true; belgeler.innerHTML = "";
  ilerleme.hidden = false; dolgu.style.width = "0%";
  ilerlemeMetin.textContent = "Arama başlatılıyor…";
  btn.disabled = true;

  const istek = {
    kelime: document.getElementById("kelime").value.trim(),
    adet: parseInt(document.getElementById("adet").value, 10),
    arama_tipi: document.querySelector("input[name=tip]:checked").value,
    dava_basina: parseInt(document.getElementById("dava_basina").value, 10),
  };

  try {
    const r = await fetch("/ara", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(istek),
    });
    const { job_id } = await r.json();
    yokla(job_id, istek.adet);
  } catch (err) {
    gosterHata("İstek gönderilemedi: " + err);
  }
});

async function yokla(jobId, istenen) {
  try {
    const r = await fetch(`/durum/${jobId}`);
    const j = await r.json();
    const hedef = j.hedef || istenen;
    const yuzde = hedef ? Math.round((j.indirilen / hedef) * 100) : 0;
    dolgu.style.width = yuzde + "%";
    ilerlemeMetin.textContent = `${j.indirilen}/${hedef} karar indirildi (${j.durum})`;

    if (j.durum === "bitti") { bitir(jobId, j.ozet, istenen); return; }
    if (j.durum === "hata") { gosterHata(j.hata || "bilinmeyen hata"); return; }
    setTimeout(() => yokla(jobId, istenen), 1000);
  } catch (err) {
    gosterHata("Durum alınamadı: " + err);
  }
}

function bitir(jobId, ozet, istenen) {
  ilerleme.hidden = true;
  sonuc.hidden = false;
  btn.disabled = false;
  let mesaj = `Tamamlandı — İstenen ${ozet.istenen}, bulunan ${ozet.toplanan} dava, `
            + `${ozet.belge_sayisi} PDF belge üretildi.`;
  if (ozet.eksik_uyarisi) mesaj += ` (${ozet.eksik_uyarisi} — sorun değil.)`;
  if (ozet.atlanan) mesaj += ` ${ozet.atlanan} karar metni alınamadı, atlandı.`;
  ozetMetin.textContent = mesaj;
  for (const dosya of ozet.belgeler) {
    const li = document.createElement("li");
    const a = document.createElement("a");
    a.href = `/indir/${jobId}/${dosya}`;
    a.textContent = dosya;
    a.setAttribute("download", dosya);
    li.appendChild(a);
    belgeler.appendChild(li);
  }
}

function gosterHata(mesaj) {
  ilerleme.hidden = true;
  btn.disabled = false;
  hata.hidden = false;
  hata.textContent = "Hata: " + mesaj;
}
