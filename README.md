# Yargıtay Karar Toplayıcı

`karararama.yargitay.gov.tr`'den arama kelimesiyle Yargıtay kararlarını toplar,
her 10 kararı 1 PDF belgesi yapar. Web arayüzü + MCP sunucusu.

## Kurulum
    python3 -m venv .venv
    .venv/bin/pip install -r requirements.txt
    # (opsiyonel, daha kaliteli PDF): .venv/bin/pip install -r requirements-optional.txt

## Web arayüzü
Sunucu bu makinede (vespula-server, Tailscale IP `100.65.191.13`) çalışır; port
rehberine göre bu projeye **Blok #11 (4200–4219)** tahsis edildi, servis **4200**'de.

    nohup .venv/bin/python3 -m uvicorn web.app:app --host 0.0.0.0 --port 4200 > /tmp/yargitay_web.log 2>&1 &
    disown

Tailscale bağlı herhangi bir cihazdan: **http://100.65.191.13:4200** → kelime + dava
sayısı gir, Başlat. (Yerelden: `http://127.0.0.1:4200`.)
Belgeler `output/<arama>/<tarih>/belge_01.pdf …` altına yazılır.

Durdurmak için: `pkill -f "uvicorn web.app"`.

> Not: Şu an `nohup` ile çalışıyor, systemd servisi değil — sunucu reboot
> olursa otomatik kalkmaz. Kalıcı olması isteniyorsa bir `systemd --user`
> servisi tanımlanabilir (diğer projelerdeki `*.service` örnekleri gibi).

## MCP (Claude'a ekleme)
    {"mcpServers":{"yargitay":{"command":"/home/goksel/yargitay_mcp/.venv/bin/python3","args":["/home/goksel/yargitay_mcp/mcp_server.py"]}}}
Araçlar: `yargitay_ara`, `yargitay_belge_uret`, `yargitay_karar_getir`.

## Notlar
- İstenen dava sayısından az bulunması hata değildir; özet ve arayüz farkı bildirir.
- `getDokuman` (karar indirme) sık/hızlı ardışık isteklerde HTTP 429 (Too Many
  Requests) döndürür (gerçek API'de doğrulandı). Pipeline her indirme arasında
  otomatik olarak bekler ve 429'da `Retry-After` header'ına uyar; yine de
  bazen 1-2 karar atlanabilir — bu `atlanan` sayacında ve özet mesajında
  şeffaf şekilde raporlanır, iş çökmez.
- Site ayrıca bir WAF (bot tespit sistemi) kullanıyor: çok sık/hızlı otomatik
  istek gönderilirse geçici olarak CAPTCHA isteyebilir. Bu durumda araç
  anlaşılır bir hata verir ("otomatik erişimi tespit edip CAPTCHA istiyor, bir
  süre bekleyin"); CAPTCHA durumunda boşuna tekrar denenmez. Ardışık çok fazla
  arama yapmaktan kaçının.
- Test: `.venv/bin/python3 -m pytest` (birim, ağsız), `.venv/bin/python3 -m pytest -m integration` (gerçek API'ye vurur).

## Doğrulanmış API detayları
- Arama: `POST /aramadetaylist`, gövde `{"data": {"arananKelime": ..., "pageSize", "pageNumber", ...}}`.
  Tam ifade aranırken `arananKelime` çift tırnak içine alınır.
- Belge: `GET /getDokuman?id=<id>` → `{"data": "<html>...</html>"}`.
- Site önce anasayfa ziyaretiyle alınan bir WAF çerezi (`TS01...`) bekler;
  `YargitayClient` bunu ilk istekten önce otomatik alır.
