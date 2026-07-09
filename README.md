# Yargıtay Karar Toplayıcı / Yargıtay Decision Collector

[Türkçe](#türkçe) | [English](#english)

---

## Türkçe

`karararama.yargitay.gov.tr` üzerinden anahtar kelimeyle Yargıtay kararlarını arayan, toplayan ve her 10 kararı bir PDF belgesine dönüştüren araç. Hem bir web arayüzü hem de bir **MCP (Model Context Protocol) sunucusu** olarak çalışır, böylece Claude gibi bir asistana doğrudan "şu konuda 20 karar bul ve PDF'lere dönüştür" diye yazabilirsiniz.

### Özellikler

- Anahtar kelimeyle geniş (kelimeler geçen) veya tam ifade araması
- Bulunan kararları otomatik toplayıp her N kararı bir PDF'e paketleme
- Tek bir kararın temizlenmiş tam metnini çekme
- Rate-limit (HTTP 429) ve bot/CAPTCHA tespitine karşı bekleyip yeniden deneme
- FastAPI tabanlı basit bir web arayüzü

### Kurulum

```bash
git clone https://github.com/RsGoksel/yargitay_mcp.git
cd yargitay_mcp
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
# Opsiyonel, daha kaliteli PDF çıktısı için:
.venv/bin/pip install -r requirements-optional.txt
```

Windows'ta venv Python yolu `.venv\Scripts\python.exe` olur.

### Kullanım

**Web arayüzü (yerel):**

```bash
.venv/bin/python3 -m uvicorn web.app:app --host 127.0.0.1 --port 8000
```

Tarayıcıdan `http://127.0.0.1:8000` açın, arama kelimesi + dava sayısı girip başlatın. Üretilen PDF'ler `output/<arama>/<tarih>/belge_01.pdf …` altına yazılır.

**MCP sunucusu (Claude'a ekleme):**

Claude Code:

```bash
claude mcp add yargitay --scope user -- <PROJE_YOLU>/.venv/bin/python3 <PROJE_YOLU>/mcp_server.py
```

Claude Desktop (`claude_desktop_config.json`):

```json
{
  "mcpServers": {
    "yargitay": {
      "command": "<PROJE_YOLU>/.venv/bin/python3",
      "args": ["<PROJE_YOLU>/mcp_server.py"]
    }
  }
}
```

Araçlar: `yargitay_ara` (liste, PDF üretmez), `yargitay_belge_uret` (toplayıp PDF'e dönüştürür), `yargitay_karar_getir` (tek kararın tam metni).

Örnek: Claude'a *"kira tespiti davası ile ilgili 20 karar bul ve PDF'lere dönüştür"* yazmanız yeterli.

### Test

```bash
.venv/bin/python3 -m pytest          # birim testler (ağsız)
.venv/bin/python3 -m pytest -m integration   # gerçek API'ye karşı
```

### Bilinmesi gerekenler

- İstenen dava sayısından az bulunması hata değildir; özet bunu `eksik_uyarisi` ile açıkça bildirir.
- Site bir WAF (bot tespit sistemi) kullanır; çok sık/hızlı istek CAPTCHA tetikleyebilir. Ardışık çok fazla arama yapmaktan kaçının.
- Üretilen PDF'ler `output/` altına yazılır ve `.gitignore` ile repoya girmez.

Daha ayrıntılı kurulum rehberi için [`KULLANIM.md`](KULLANIM.md).

---

## English

A tool that searches Turkish Court of Cassation (*Yargıtay*) decisions on `karararama.yargitay.gov.tr` by keyword, collects them, and bundles every 10 decisions into a single PDF. It runs both as a **web UI** and as an **MCP (Model Context Protocol) server**, so an assistant like Claude can be asked directly to "find 20 decisions about X and turn them into PDFs."

### Features

- Broad (any-word-matches) or exact-phrase keyword search
- Automatic collection with PDF packaging (N decisions per file)
- Fetch the cleaned full text of a single decision
- Handles rate limiting (HTTP 429) and bot/CAPTCHA detection with backoff and retry
- Lightweight FastAPI-based web UI

### Setup

```bash
git clone https://github.com/RsGoksel/yargitay_mcp.git
cd yargitay_mcp
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
# Optional, for higher-quality PDF output:
.venv/bin/pip install -r requirements-optional.txt
```

On Windows the venv Python path is `.venv\Scripts\python.exe`.

### Usage

**Web UI (local):**

```bash
.venv/bin/python3 -m uvicorn web.app:app --host 127.0.0.1 --port 8000
```

Open `http://127.0.0.1:8000`, enter a search keyword and case count, and start. Generated PDFs are written to `output/<query>/<date>/belge_01.pdf …`.

**MCP server (adding to Claude):**

Claude Code:

```bash
claude mcp add yargitay --scope user -- <PROJECT_PATH>/.venv/bin/python3 <PROJECT_PATH>/mcp_server.py
```

Claude Desktop (`claude_desktop_config.json`):

```json
{
  "mcpServers": {
    "yargitay": {
      "command": "<PROJECT_PATH>/.venv/bin/python3",
      "args": ["<PROJECT_PATH>/mcp_server.py"]
    }
  }
}
```

Tools exposed: `yargitay_ara` (search, list only, no PDF), `yargitay_belge_uret` (collect + PDF), `yargitay_karar_getir` (full text of a single decision).

Example: just ask Claude *"find 20 decisions about rent-assessment lawsuits and turn them into PDFs."*

### Tests

```bash
.venv/bin/python3 -m pytest                  # unit tests (no network)
.venv/bin/python3 -m pytest -m integration    # against the real API
```

### Good to know

- Finding fewer decisions than requested is not an error — the summary reports it via `eksik_uyarisi`.
- The site uses a WAF (bot-detection system); sending too many requests too quickly may trigger a CAPTCHA. Avoid rapid, repeated searches.
- Generated PDFs are written to `output/` and excluded from the repo via `.gitignore`.

For a more detailed setup walkthrough, see [`KULLANIM.md`](KULLANIM.md) (Turkish).

## License

No license file is currently included — all rights reserved by default. Contact the repository owner before reuse.
