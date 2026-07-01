# Yargıtay Karar Toplayıcı

`karararama.yargitay.gov.tr`'den arama kelimesiyle Yargıtay kararlarını toplar,
her 10 kararı 1 PDF belgesi yapar. Web arayüzü + MCP sunucusu.

## Kurulum
    python3 -m venv .venv
    .venv/bin/pip install -r requirements.txt
    # (opsiyonel, daha kaliteli PDF): .venv/bin/pip install -r requirements-optional.txt

## Web arayüzü
    .venv/bin/python3 -m uvicorn web.app:app --port 8477
Tarayıcıdan http://127.0.0.1:8477 → kelime + dava sayısı gir, Başlat.
Belgeler `output/<arama>/<tarih>/belge_01.pdf …` altına yazılır.

## MCP (Claude'a ekleme)
    {"mcpServers":{"yargitay":{"command":"/home/goksel/yargitay_mcp/.venv/bin/python3","args":["/home/goksel/yargitay_mcp/mcp_server.py"]}}}
Araçlar: `yargitay_ara`, `yargitay_belge_uret`, `yargitay_karar_getir`.

## Notlar
- İstenen dava sayısından az bulunması hata değildir; özet ve arayüz farkı bildirir.
- Site bir WAF (bot tespit sistemi) kullanıyor: çok sık/hızlı otomatik istek
  gönderilirse geçici olarak CAPTCHA isteyebilir. Bu durumda araç anlaşılır bir
  hata verir ("otomatik erişimi tespit edip CAPTCHA istiyor, bir süre bekleyin");
  kod otomatik olarak geçici hatalarda birkaç kez dener ama CAPTCHA durumunda
  boşuna tekrar denemez. Ardışık çok fazla arama yapmaktan kaçının.
- Test: `.venv/bin/python3 -m pytest` (birim, ağsız), `.venv/bin/python3 -m pytest -m integration` (gerçek API'ye vurur).

## Doğrulanmış API detayları
- Arama: `POST /aramadetaylist`, gövde `{"data": {"arananKelime": ..., "pageSize", "pageNumber", ...}}`.
  Tam ifade aranırken `arananKelime` çift tırnak içine alınır.
- Belge: `GET /getDokuman?id=<id>` → `{"data": "<html>...</html>"}`.
- Site önce anasayfa ziyaretiyle alınan bir WAF çerezi (`TS01...`) bekler;
  `YargitayClient` bunu ilk istekten önce otomatik alır.
