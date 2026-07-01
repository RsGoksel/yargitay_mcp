# Yargıtay Karar Toplama Aracı — Tasarım Belgesi

**Tarih:** 2026-07-01
**Konum:** `/home/goksel/yargitay_mcp`
**Durum:** Onaylandı (2026-07-01)

## 1. Amaç

Bir kullanıcı bir hukukî konuyla ilgili arama kelimesi ve kaç adet dava istediğini
girer. Araç `karararama.yargitay.gov.tr` üzerinden ilgili Yargıtay kararlarını toplar,
**her 10 kararı 1 PDF belgesine** gruplayarak indirilebilir belgeler üretir.

- İstenen dava sayısı seçilebilir (örn. 10, 50, 100).
- Bulunan sayı istenenden az olabilir (100 istenir, 20 çıkar) — bu bir hata değildir;
  araç eldeki kadarını üretir ve **istenen vs bulunan** farkını açıkça bildirir.
- İki yüz: (a) tarayıcıda açılan yerel **web arayüzü** (insan için), (b) Claude/AI'ın
  kullanacağı **MCP sunucusu**. İkisi de aynı çekirdek motoru kullanır.

## 2. Doğrulanmış API gerçekleri (2026-07-01 test edildi)

**Arama** — `POST https://karararama.yargitay.gov.tr/aramadetaylist`
Content-Type: `application/json`. Gövde:

```json
{"data":{
  "arananKelime":"kira tespiti",
  "esasYil":"","esasIlkSiraNo":"","esasSonSiraNo":"",
  "kararYil":"","kararIlkSiraNo":"","kararSonSiraNo":"",
  "baslangicTarihi":"","bitisTarihi":"",
  "siralama":"3","siralamaDirection":"desc",
  "birimYrgKurulDaire":"","birimYrgHukukDaire":"","birimYrgCezaDaire":"",
  "pageSize":10,"pageNumber":1
}}
```

Başarılı yanıt:
```json
{"data":{"data":[
  {"id":"1213744300","daire":"1. Ceza Dairesi","esasNo":"2025/7182",
   "kararNo":"2026/4176","kararTarihi":"21.05.2026","arananKelime":"kira tespiti",
   "index":1,"siraNo":1}, ...
 ],"recordsTotal":2267023,"recordsFiltered":2267023},
 "metadata":{"FMTY":"SUCCESS", ...}}
```

- `recordsTotal` → toplam eşleşen karar sayısı (**bulunan** için bunu kullan).
- `pageSize` büyük tutulabilir (test: 3 çalıştı; pratikte 100'e kadar denenip
  paginasyon ile ilerlenecek). `pageNumber` 1'den başlar.
- Yanlış/eksik gövde → HTTP 200 ama `metadata.FMTY == "ERROR"` döner. Bu yüzden
  başarı `metadata.FMTY == "SUCCESS"` ile kontrol edilmeli, sadece HTTP koduyla değil.

**Belge** — `GET https://karararama.yargitay.gov.tr/getDokuman?id=<id>`
Yanıt: `{"data":"<html>...tam karar metni...</html>"}`. HTML gövdesi `<font>`/`<br>`
etiketleriyle doludur; düz metne / temiz PDF'e dönüştürülecek. UTF-8, Türkçe karakterli.

**Arama tipi eşlemesi (kullanıcı seçimi):**
- *Geniş arama:* `arananKelime` düz kelimeler (varsayılan site davranışı).
- *Tam ifade:* `arananKelime` çift tırnak içinde gönderilir, örn. `"\"kira tespiti\""`.
  (Site sözdizimi; uygulama sırasında tam-ifade sonucu boşsa geniş aramaya düşme
  YAPMA — kullanıcı bilinçli seçti, farkı özet raporunda belirt.)

## 3. Mimari — tek çekirdek, iki yüz

```
yargitay_mcp/
  core/
    __init__.py
    config.py       # sabitler: BASE_URL, endpoint yolları, timeout, eşzamanlılık,
                    #          varsayılan dava_basina=10, User-Agent
    models.py       # Karar (dataclass): id, daire, esasNo, kararNo, kararTarihi,
                    #          arananKelime, metin(html/temiz)
    client.py       # YargitayClient: ara(...) ve karar_getir(id)
                    #   - retry + exponential backoff, kibar gecikme
                    #   - metadata.FMTY kontrolü
    renderer.py     # PdfRenderer arayüzü + WeasyPrintRenderer (birincil)
                    #   + Fpdf2Renderer (yedek). get_renderer() otomatik seçer.
    pipeline.py     # collect_and_build(): tüm akışı yürütür, ilerleme callback'i alır
  mcp_server.py     # MCP stdio sunucusu — 3 araç (bkz. §6)
  web/
    app.py          # FastAPI: iş başlat / ilerleme / PDF indir
    static/
      index.html    # tek sayfa arayüz
      app.js        # form + ilerleme polling + sonuç listesi
      style.css
  output/           # <arama-slug>/<YYYY-MM-DD_HH-MM-SS>/belge_01.pdf ... + ozet.json
  tests/
    fixtures/       # kaydedilmiş API yanıtları (aramalist + getDokuman örnekleri)
    test_client.py test_pipeline.py test_renderer.py test_grouping.py
  requirements.txt
  README.md
```

**Sorumluluk sınırları:**
- `client.py` HTTP'yi bilir, PDF/gruplama bilmez.
- `pipeline.py` iş akışını bilir, HTTP detayını/PDF motorunu bilmez (client + renderer'a delege).
- `renderer.py` sadece "kararlar → PDF dosyası" bilir.
- `mcp_server.py` ve `web/app.py` yalnızca ince kabuk; ikisi de `pipeline.collect_and_build()` çağırır.

## 4. Veri akışı (pipeline.collect_and_build)

Girdi: `kelime, adet, arama_tipi, dava_basina=10, ilerleme_cb=None`.

1. **Ara + sayfala:** `adet` kadar karar metadata toplanana veya kayıtlar bitene kadar
   `client.ara()` çağır (pageSize örn. 100). İlk yanıttaki `recordsTotal` → `bulunabilir`.
   Toplanan = `min(adet, bulunabilir)`.
2. **İndir:** her `id` için `client.karar_getir(id)` (kibar eşzamanlılık ~3, backoff+retry).
   Her indirmede `ilerleme_cb(indirilen, hedef)` çağır.
3. **Temizle:** karar HTML'ini oku (`data` alanı), gövdeyi çıkar, `<br>`→satır sonu,
   etiket temizliği, whitespace normalize.
4. **Grupla:** kararları sırayla `dava_basina`'lık dilimlere böl
   (100 karar, 10'ar → 10 belge; sonuncusu 4 karar içerebilir).
5. **Render:** her dilim → `belge_NN.pdf`. Her karar başlığı: `daire`, `esasNo E. /
   kararNo K.`, `kararTarihi`, üstte arama kelimesi ve "Dava k/toplam".
6. **Özet yaz:** `ozet.json`:
   ```json
   {"arama":"kira tespiti","arama_tipi":"tam",
    "istenen":100,"bulunabilir_toplam":2267023,"toplanan":100,
    "dava_basina":10,"belge_sayisi":10,
    "eksik_uyarisi":null,
    "belgeler":["belge_01.pdf", ...],
    "tarih":"2026-07-01T13:20:00"}
   ```
   `toplanan < istenen` ise `eksik_uyarisi` doldurulur
   (`"100 istendi, 20 bulundu"`). Fonksiyon bu özeti döndürür.

## 5. Web arayüzü

**Tek sayfa** (`static/index.html`), sade ve okunaklı:
- Form: arama kelimesi (metin), dava sayısı (sayı, varsayılan 10),
  arama tipi (radyo: *Geniş* / *Tam ifade*), belge başına dava (sayı, varsayılan 10,
  gelişmiş/katlanır), opsiyonel daire filtresi (açılır liste — sonraki sürümde
  doldurulabilir, ilk sürümde boş=tümü). "Başlat" düğmesi.
- **Arka plan işi:** `POST /ara` bir `job_id` döner. İş `pipeline`'ı arka planda çalıştırır
  (FastAPI BackgroundTasks + bellek-içi job kaydı: durum, indirilen/hedef, sonuç/hata).
- **İlerleme:** arayüz `GET /durum/{job_id}`'yi ~1sn'de bir yoklar; çubuk `23/100 indirildi`
  gösterir.
- **Bitiş:** durum `bitti` olunca sonuç kartı: **"İstenen 100 — Bulunan 20 (sorun değil)"**
  net şekilde, ardından üretilen PDF'ler için indirme linkleri (`GET /indir/{job_id}/{dosya}`).
- Hata olursa arayüzde okunaklı hata mesajı.

Uçlar:
- `POST /ara` → `{kelime, adet, arama_tipi, dava_basina}` → `{job_id}`
- `GET /durum/{job_id}` → `{durum, indirilen, hedef, ozet?, hata?}`
- `GET /indir/{job_id}/{dosya}` → PDF dosyası
- `GET /` → statik arayüz

## 6. MCP araçları

MCP Python SDK (`mcp`) ile stdio sunucusu. Üç araç:

- `yargitay_ara(kelime: str, adet: int = 10, arama_tipi: "genis"|"tam" = "genis",
  daire: str = "")` → `{bulunabilir_toplam, kararlar:[{id,daire,esasNo,kararNo,kararTarihi}]}`.
  Sadece metadata; PDF üretmez. Hızlı önizleme/keşif için.
- `yargitay_belge_uret(kelime: str, adet: int = 10, arama_tipi = "genis",
  dava_basina: int = 10, daire: str = "")` → tüm pipeline'ı çalıştırır,
  `ozet.json` içeriğini + üretilen PDF mutlak yollarını döner.
- `yargitay_karar_getir(id: str)` → tek kararın temizlenmiş tam metni.

MCP kayıt örneği (kullanıcının Claude'una eklemesi için README'de):
```json
{"mcpServers":{"yargitay":{"command":"python","args":["/home/goksel/yargitay_mcp/mcp_server.py"]}}}
```

## 7. Sağlamlık kararları

- **Az sonuç hata değil:** her yerde `toplanan < istenen` normal akış; özet + arayüz belirtir.
- **PDF motoru fallback:** `get_renderer()` önce WeasyPrint'i dener (import + minik test
  render). Başarısızsa (sistem kütüphanesi yok vb.) `fpdf2` + DejaVu Sans (Türkçe glif)
  yedeğine düşer. İkisi de aynı `PdfRenderer.render(kararlar, cikti_yolu, baslik)`
  arayüzünü uygular. Sonnet takılırsa: fallback zaten var, motor seçimini loglar.
- **Kibarlık & dayanıklılık:** istekler arası küçük gecikme (örn. 0.3–0.5sn),
  eşzamanlılık ≤3, HTTP hatalarında exponential backoff ile ≤3 tekrar, gerçekçi
  `User-Agent`. `metadata.FMTY=="ERROR"` yakalanır ve anlamlı hata verir.
- **Boş/kısmi indirme:** bir kararın metni alınamazsa o karar atlanır ama sayılır
  (özet notuna eklenir), tüm iş çökmemeli.
- **Dosya adları:** arama-slug ASCII'ye indirgenir (Türkçe karakter → düz), timestamp
  klasörü çakışmayı önler.

## 8. Test (TDD)

- `tests/fixtures/` altına gerçek bir arama yanıtı ve bir `getDokuman` yanıtı kaydedilir.
- **Birim testleri (mock'lu, ağsız):**
  - `test_grouping`: N karar `dava_basina`'ya göre doğru belge sayısına bölünür
    (100/10=10; 23/10=3, son belge 3 karar; 0 karar → 0 belge).
  - `test_pipeline`: `toplanan < istenen` → `eksik_uyarisi` doğru dolar; özet alanları doğru.
  - `test_client`: fixture'la ara() parse, `metadata.FMTY=="ERROR"` → istisna,
    tam-ifade tırnaklama doğru gövde üretir.
  - `test_renderer`: verilen kararlarla PDF dosyası oluşur, boş değil, Türkçe metin gömülü
    (fallback renderer üzerinden deterministik test).
- **Entegrasyon testi (ağ):** `@pytest.mark.integration` ile işaretli, gerçek API'ye
  1 küçük arama + 1 belge indirir; varsayılan test koşusunda atlanır.

## 9. Teknoloji

- Python 3 (ortamda mevcut). Bağımlılıklar (`requirements.txt`):
  `mcp`, `fastapi`, `uvicorn`, `requests` (veya `httpx`), `weasyprint`, `fpdf2`,
  `beautifulsoup4` (HTML temizleme), `pytest`.
- Web arayüzü çerçevesiz (vanilla JS + fetch); ekstra frontend derlemesi yok.

## 10. Kapsam dışı (YAGNI — ilk sürüm)

- Kullanıcı hesabı / kimlik doğrulama.
- Daire filtresi listesinin otomatik doldurulması (alan bırakılır, sonra eklenebilir).
- Kararların tam-metin yerel arama/indeksleme.
- Danıştay/UYAP gibi diğer kaynaklar (yalnızca Yargıtay).
