# Kendi Bilgisayarında Kullanım Kılavuzu

Bu kılavuz, `yargitay_mcp`'yi **kendi lokal makinende** (sunucudan bağımsız)
kurup hem web arayüzü hem MCP olarak kullanman için.

## 1. Gereksinimler

- Python 3.10+ (`python3 --version` ile kontrol et)
- Git

## 2. Repoyu indir

    git clone https://github.com/RsGoksel/yargitay_mcp.git
    cd yargitay_mcp

(Repo private — klonlamak için GitHub hesabınla giriş yapmış/yetkili olman gerekir.)

## 3. Kurulum

Debian/Ubuntu gibi sistemlerde sistem Python'ı paket kurmayı engelleyebilir
(`externally-managed-environment` hatası) — bu yüzden sanal ortam (venv) şart:

    python3 -m venv .venv
    .venv/bin/pip install --upgrade pip
    .venv/bin/pip install -r requirements.txt

Opsiyonel, daha kaliteli PDF çıktısı istersen (sistemde ek kütüphane ister,
kurulamazsa kod otomatik `fpdf2`'ye düşer, sorun olmaz):

    .venv/bin/pip install -r requirements-optional.txt

## 4. Testleri çalıştır (opsiyonel ama önerilir)

    .venv/bin/python3 -m pytest -v

Hepsi geçmeli (ağa çıkmayan birim testleri). Gerçek Yargıtay API'sine karşı
tek seferlik doğrulama istersen:

    .venv/bin/python3 -m pytest -m integration -v

## 5. Web arayüzünü yerelde çalıştır

    .venv/bin/python3 -m uvicorn web.app:app --host 127.0.0.1 --port 8000

Tarayıcıdan **http://127.0.0.1:8000** aç → arama kelimesi + dava sayısı gir,
Başlat. Üretilen PDF'ler `output/<arama>/<tarih>/belge_01.pdf …` altına yazılır.

Durdurmak için terminalde `Ctrl+C`.

> Port `8000` keyfi seçildi — kendi makinende port çakışması olursa `--port`
> değerini değiştir, başka bir kısıtlama yok (port bloğu kuralı sadece
> vespula-server'a özeldi).

## 6. MCP olarak Claude'a bağlama

Önce kurulumun tam yolunu öğren (aşağıdaki komutlarda `<PROJE_YOLU>` yerine
kullan, örn. `/home/kullanici/yargitay_mcp` veya `C:\Users\...\yargitay_mcp`):

    pwd   # Linux/macOS
    cd    # Windows (cmd) — mevcut dizini gösterir

### Claude Code (CLI) kullanıyorsan

    claude mcp add yargitay --scope user -- <PROJE_YOLU>/.venv/bin/python3 <PROJE_YOLU>/mcp_server.py

Windows'ta venv Python yolu `.venv\Scripts\python.exe` olur.

### Claude Desktop (masaüstü uygulaması) kullanıyorsan

Ayar dosyasını aç:
- **macOS:** `~/Library/Application Support/Claude/claude_desktop_config.json`
- **Windows:** `%APPDATA%\Claude\claude_desktop_config.json`
- **Linux:** `~/.config/Claude/claude_desktop_config.json`

İçine (veya var olan `mcpServers` bloğuna) ekle:

    {
      "mcpServers": {
        "yargitay": {
          "command": "<PROJE_YOLU>/.venv/bin/python3",
          "args": ["<PROJE_YOLU>/mcp_server.py"]
        }
      }
    }

Windows'ta `command` değeri `<PROJE_YOLU>\\.venv\\Scripts\\python.exe` olmalı
(ters slash'ları `\\` olarak kaçırman gerekir, JSON içinde).

Kaydettikten sonra Claude Desktop'ı yeniden başlat. Araçlar Claude'a otomatik
görünür: `yargitay_ara`, `yargitay_belge_uret`, `yargitay_karar_getir`.

## 7. Kullanım örneği (MCP üzerinden, Claude'a yazarak)

> "kira tespiti davası ile ilgili 20 karar bul ve PDF'lere dönüştür"

Claude bunun için `yargitay_belge_uret(kelime="kira tespiti", adet=20)` aracını
çağırır; sonuçta üretilen PDF'lerin tam yolunu sana döner (`output/` altında).

## 8. Bilinmesi gerekenler

- **İstenen sayıdan az bulunması hata değildir** — özet bunu açıkça belirtir.
- Yargıtay sitesi hız sınırlaması (HTTP 429) ve bot-tespit (CAPTCHA)
  kullanıyor. Kod nazikçe bekleyip tekrar dener; yine de bazen birkaç karar
  atlanabilir (`atlanan` sayacında görünür) veya CAPTCHA tetiklenirse net bir
  hata mesajı alırsın. **Art arda çok fazla/hızlı arama yapmaktan kaçın.**
- `output/` klasörü `.gitignore`'da — üretilen PDF'ler repoya girmez, sadece
  senin diskinde kalır.
