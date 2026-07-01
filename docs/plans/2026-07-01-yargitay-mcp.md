# Yargıtay Karar Toplama Aracı — Uygulama Planı

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** `karararama.yargitay.gov.tr`'den arama kelimesiyle Yargıtay kararlarını toplayıp her 10 kararı 1 PDF belgesi yapan; hem yerel web arayüzü hem MCP sunucusu olan bir araç.

**Architecture:** Tek Python çekirdeği (`core/`) — HTTP istemcisi, HTML temizleme, gruplama, PDF renderer, pipeline. Üstünde iki ince kabuk: `mcp_server.py` (Claude için stdio MCP) ve `web/app.py` (insan için FastAPI + tek sayfa arayüz). İkisi de aynı `pipeline.collect_and_build()`'i çağırır.

**Tech Stack:** Python 3, `requests`, `beautifulsoup4`, `fpdf2` (garanti PDF), opsiyonel `weasyprint` (daha kaliteli PDF), `mcp` (FastMCP), `fastapi` + `uvicorn`, `pytest`.

## Global Constraints

- Proje kökü: `/home/goksel/yargitay_mcp`. Tüm yollar buna göre.
- Ortam git deposu **değil** — commit adımları için önce `git init` (Task 0). Commit'ler yerel, push yok.
- Arama başarısı `metadata.FMTY == "SUCCESS"` ile kontrol edilir; sadece HTTP 200 yeterli değildir (hatalı gövde de 200 döner).
- Az sonuç bir hata değildir: `toplanan < istenen` normal akıştır; her yerde özet + arayüzde açıkça bildirilir, eldeki kadar üretilir.
- PDF: `fpdf2` **garanti yol** (varsayılan). `weasyprint` varsa otomatik tercih edilir; yoksa/başarısızsa sessizce `fpdf2`'ye düşülür. Sonnet weasyprint kurulumuna takılmasın — opsiyoneldir.
- Türkçe karakter: fpdf2 için DejaVu Sans TTF gömülür (Debian'da `/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf`).
- Kibarlık: istekler arası ~0.35sn gecikme, eşzamanlılık ≤3, HTTP hatasında ≤3 tekrar (exponential backoff), gerçekçi User-Agent.
- Varsayılanlar: `dava_basina=10`, `page_size=100`, `arama_tipi="genis"`.
- v1 kapsamı: daire filtresi YOK (tüm daireler). Kimlik doğrulama YOK. Sadece Yargıtay.
- Testler ağsız çalışır (mock/fixture). Gerçek API'ye vuran test `@pytest.mark.integration` ile işaretli ve varsayılan koşuda atlanır.

---

## File Structure

```
yargitay_mcp/
  core/__init__.py
  core/config.py        # sabitler + yol/slug/timestamp yardımcıları
  core/models.py        # Karar dataclass
  core/client.py        # YargitayClient (ara, ara_topla, karar_getir) + temizle()
  core/grouping.py      # grupla()
  core/renderer.py      # PdfRenderer arayüzü + Fpdf2Renderer + WeasyPrintRenderer + get_renderer()
  core/pipeline.py      # collect_and_build()
  mcp_server.py         # FastMCP: 3 araç
  web/app.py            # FastAPI: /ara /durum /indir /
  web/static/index.html
  web/static/app.js
  web/static/style.css
  output/               # üretilen PDF'ler (gitignore)
  tests/conftest.py
  tests/fixtures/arama.json
  tests/fixtures/dokuman.json
  tests/test_client.py
  tests/test_grouping.py
  tests/test_renderer.py
  tests/test_pipeline.py
  tests/test_integration.py
  requirements.txt
  requirements-optional.txt
  README.md
  .gitignore
  pytest.ini
```

---

### Task 0: Proje iskeleti, bağımlılıklar, git

**Files:**
- Create: `requirements.txt`, `requirements-optional.txt`, `.gitignore`, `pytest.ini`, `core/__init__.py`, `tests/__init__.py`

**Interfaces:**
- Produces: kurulu Python ortamı + boş paket iskeleti.

- [ ] **Step 1: git init ve paket klasörleri**

```bash
cd /home/goksel/yargitay_mcp
git init
mkdir -p core web/static tests/fixtures output
touch core/__init__.py tests/__init__.py
```

- [ ] **Step 2: requirements dosyaları**

`requirements.txt`:
```
requests>=2.31
beautifulsoup4>=4.12
fpdf2>=2.7
mcp>=1.2.0
fastapi>=0.110
uvicorn>=0.29
pytest>=8.0
```

`requirements-optional.txt` (daha kaliteli PDF; sistem kütüphanesi gerektirir, zorunlu değil):
```
weasyprint>=60
```

- [ ] **Step 3: .gitignore, pytest.ini**

`.gitignore`:
```
__pycache__/
*.pyc
output/
.venv/
*.egg-info/
```

`pytest.ini`:
```
[pytest]
markers =
    integration: gerçek Yargıtay API'sine bağlanır (varsayılan koşuda atlanır)
addopts = -m "not integration"
```

- [ ] **Step 4: Bağımlılıkları kur**

```bash
cd /home/goksel/yargitay_mcp
python3 -m pip install -r requirements.txt
```
Beklenen: hepsi başarıyla kurulur. (weasyprint kurma — opsiyonel.)

- [ ] **Step 5: Commit**

```bash
git add -A && git commit -m "chore: proje iskeleti ve bağımlılıklar"
```

---

### Task 1: config ve models

**Files:**
- Create: `core/config.py`, `core/models.py`
- Test: `tests/test_grouping.py` içinde dolaylı; burada doğrudan test yok (saf sabit/veri).

**Interfaces:**
- Produces:
  - `config.BASE_URL, ARAMA_ENDPOINT, DOKUMAN_ENDPOINT, USER_AGENT, TIMEOUT, MAX_RETRIES, CONCURRENCY, REQUEST_DELAY, DEFAULT_PAGE_SIZE, DEFAULT_DAVA_BASINA, OUTPUT_DIR`
  - `config.slug(s: str) -> str`, `config.timestamp() -> str`, `config.arama_govdesi(kelime, arama_tipi, page_size, page_number) -> dict`
  - `models.Karar` dataclass: alanlar `id, daire, esasNo, kararNo, kararTarihi, arananKelime, metin`; sınıf metodu `Karar.from_arama(d: dict) -> Karar`.

- [ ] **Step 1: core/config.py yaz**

```python
import re
import unicodedata
from datetime import datetime
from pathlib import Path

BASE_URL = "https://karararama.yargitay.gov.tr"
ARAMA_ENDPOINT = "/aramadetaylist"
DOKUMAN_ENDPOINT = "/getDokuman"
USER_AGENT = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/125.0 Safari/537.36"
)
TIMEOUT = 30
MAX_RETRIES = 3
CONCURRENCY = 3
REQUEST_DELAY = 0.35
DEFAULT_PAGE_SIZE = 100
DEFAULT_DAVA_BASINA = 10
OUTPUT_DIR = Path(__file__).resolve().parent.parent / "output"


def slug(s: str) -> str:
    """Türkçe arama kelimesini güvenli ASCII klasör adına indirger."""
    s = s.strip().lower()
    tr = str.maketrans("çğıöşü", "cgiosu")
    s = s.translate(tr)
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode()
    s = re.sub(r"[^a-z0-9]+", "-", s).strip("-")
    return s or "arama"


def timestamp() -> str:
    return datetime.now().strftime("%Y-%m-%d_%H-%M-%S")


def arama_govdesi(kelime: str, arama_tipi: str, page_size: int, page_number: int) -> dict:
    aranan = f'"{kelime}"' if arama_tipi == "tam" else kelime
    return {"data": {
        "arananKelime": aranan,
        "esasYil": "", "esasIlkSiraNo": "", "esasSonSiraNo": "",
        "kararYil": "", "kararIlkSiraNo": "", "kararSonSiraNo": "",
        "baslangicTarihi": "", "bitisTarihi": "",
        "siralama": "3", "siralamaDirection": "desc",
        "birimYrgKurulDaire": "", "birimYrgHukukDaire": "", "birimYrgCezaDaire": "",
        "pageSize": page_size, "pageNumber": page_number,
    }}
```

- [ ] **Step 2: core/models.py yaz**

```python
from dataclasses import dataclass


@dataclass
class Karar:
    id: str
    daire: str = ""
    esasNo: str = ""
    kararNo: str = ""
    kararTarihi: str = ""
    arananKelime: str = ""
    metin: str = ""

    @classmethod
    def from_arama(cls, d: dict) -> "Karar":
        return cls(
            id=str(d.get("id", "")),
            daire=d.get("daire", "") or "",
            esasNo=d.get("esasNo", "") or "",
            kararNo=d.get("kararNo", "") or "",
            kararTarihi=d.get("kararTarihi", "") or "",
            arananKelime=d.get("arananKelime", "") or "",
        )
```

- [ ] **Step 3: İçe aktarmayı doğrula**

Run: `cd /home/goksel/yargitay_mcp && python3 -c "from core.config import slug, arama_govdesi; from core.models import Karar; print(slug('Kira Tespiti çğş'), Karar.from_arama({'id':1,'daire':'X'}))"`
Expected: `kira-tespiti-cgs Karar(id='1', daire='X', ...)`

- [ ] **Step 4: Commit**

```bash
git add -A && git commit -m "feat: config sabitleri ve Karar modeli"
```

---

### Task 2: Test fixture'ları

**Files:**
- Create: `tests/fixtures/arama.json`, `tests/fixtures/dokuman.json`, `tests/conftest.py`

**Interfaces:**
- Produces: `conftest.py` fixture'ları `arama_yaniti` (dict) ve `dokuman_yaniti` (dict); testlerin ağa çıkmadan gerçekçi veri kullanması.

- [ ] **Step 1: Gerçek API'den küçük örnek kaydet**

```bash
cd /home/goksel/yargitay_mcp
curl -s 'https://karararama.yargitay.gov.tr/aramadetaylist' \
  -H 'Content-Type: application/json' -H 'User-Agent: Mozilla/5.0' \
  --data '{"data":{"arananKelime":"kira tespiti","esasYil":"","esasIlkSiraNo":"","esasSonSiraNo":"","kararYil":"","kararIlkSiraNo":"","kararSonSiraNo":"","baslangicTarihi":"","bitisTarihi":"","siralama":"3","siralamaDirection":"desc","birimYrgKurulDaire":"","birimYrgHukukDaire":"","birimYrgCezaDaire":"","pageSize":5,"pageNumber":1}}' \
  -o tests/fixtures/arama.json
# İlk id'yi al ve dokümanını kaydet
ID=$(python3 -c "import json;print(json.load(open('tests/fixtures/arama.json'))['data']['data'][0]['id'])")
curl -s "https://karararama.yargitay.gov.tr/getDokuman?id=$ID" -H 'User-Agent: Mozilla/5.0' -o tests/fixtures/dokuman.json
```
Expected: iki dosya oluşur, `arama.json` içinde `metadata.FMTY == "SUCCESS"`, `dokuman.json` içinde `data` HTML metni.

- [ ] **Step 2: conftest.py yaz**

```python
import json
from pathlib import Path
import pytest

FIX = Path(__file__).parent / "fixtures"


@pytest.fixture
def arama_yaniti():
    return json.loads((FIX / "arama.json").read_text(encoding="utf-8"))


@pytest.fixture
def dokuman_yaniti():
    return json.loads((FIX / "dokuman.json").read_text(encoding="utf-8"))
```

- [ ] **Step 3: Fixture'ların yüklendiğini doğrula**

Run: `cd /home/goksel/yargitay_mcp && python3 -c "import json; d=json.load(open('tests/fixtures/arama.json')); print(d['metadata']['FMTY'], len(d['data']['data']))"`
Expected: `SUCCESS 5`

- [ ] **Step 4: Commit**

```bash
git add -A && git commit -m "test: gerçek API fixture'ları ve conftest"
```

---

### Task 3: YargitayClient + HTML temizleme

**Files:**
- Create: `core/client.py`
- Test: `tests/test_client.py`

**Interfaces:**
- Consumes: `config` (endpointler, `arama_govdesi`, sabitler), `models.Karar`.
- Produces:
  - `client.temizle(html: str) -> str` — HTML karar metnini düz metne çevirir.
  - `client.YargitayError(Exception)`
  - `client.YargitayClient(session=None)` metotları:
    - `ara(kelime, arama_tipi="genis", page_size=100, page_number=1) -> dict` → `{"toplam": int, "kararlar": list[Karar]}`
    - `ara_topla(kelime, adet, arama_tipi="genis", ilerleme_cb=None) -> dict` → `{"toplam": int, "kararlar": list[Karar]}` (adet kadar, sayfalayarak)
    - `karar_getir(id: str) -> str` — temizlenmiş tam metin

- [ ] **Step 1: Failing testleri yaz — tests/test_client.py**

```python
import pytest
from unittest.mock import MagicMock
from core.client import YargitayClient, YargitayError, temizle


def _fake_session(json_payloads):
    """Her POST/GET çağrısında sıradaki payload'ı döndüren sahte session."""
    session = MagicMock()
    resp_list = []
    for p in json_payloads:
        r = MagicMock()
        r.status_code = 200
        r.json.return_value = p
        r.raise_for_status.return_value = None
        resp_list.append(r)
    session.post.side_effect = resp_list
    session.get.side_effect = resp_list
    return session


def test_temizle_br_ve_etiket(arama_yaniti):
    html = '<html><body><b>Başlık</b><br>Satır1<br>Satır2</body></html>'
    metin = temizle(html)
    assert "Başlık" in metin
    assert "Satır1\nSatır2" in metin
    assert "<" not in metin


def test_ara_parse(arama_yaniti):
    client = YargitayClient(session=_fake_session([arama_yaniti]))
    sonuc = client.ara("kira tespiti")
    assert sonuc["toplam"] == arama_yaniti["data"]["recordsTotal"]
    assert len(sonuc["kararlar"]) == len(arama_yaniti["data"]["data"])
    assert sonuc["kararlar"][0].id == str(arama_yaniti["data"]["data"][0]["id"])


def test_ara_hata_metadata():
    hatali = {"data": None, "metadata": {"FMTY": "ERROR", "FMTE": "Hata Oluştu!"}}
    client = YargitayClient(session=_fake_session([hatali]))
    with pytest.raises(YargitayError):
        client.ara("x")


def test_tam_ifade_tirnaklar(monkeypatch, arama_yaniti):
    client = YargitayClient(session=_fake_session([arama_yaniti]))
    captured = {}
    orig = client.session.post
    def spy(url, **kw):
        captured["body"] = kw.get("json")
        return orig(url, **kw)
    client.session.post = spy
    client.ara("kira tespiti", arama_tipi="tam")
    assert captured["body"]["data"]["arananKelime"] == '"kira tespiti"'


def test_ara_topla_sayfalama(arama_yaniti):
    # 5'er kayıtlık iki sayfa → 8 istenirse 8 döner
    client = YargitayClient(session=_fake_session([arama_yaniti, arama_yaniti]))
    sonuc = client.ara_topla("kira", adet=8, arama_tipi="genis")
    assert len(sonuc["kararlar"]) == 8
```

- [ ] **Step 2: Testleri çalıştır, başarısızlığı gör**

Run: `cd /home/goksel/yargitay_mcp && python3 -m pytest tests/test_client.py -v`
Expected: FAIL — `ModuleNotFoundError: core.client` / import hatası.

- [ ] **Step 3: core/client.py yaz**

```python
import time
import requests
from bs4 import BeautifulSoup

from . import config
from .models import Karar


class YargitayError(Exception):
    pass


def temizle(html: str) -> str:
    soup = BeautifulSoup(html or "", "html.parser")
    for br in soup.find_all("br"):
        br.replace_with("\n")
    text = soup.get_text()
    # satır sonlarını normalize et, aşırı boş satırları daralt
    lines = [ln.rstrip() for ln in text.splitlines()]
    out, blank = [], 0
    for ln in lines:
        if ln.strip() == "":
            blank += 1
            if blank <= 1:
                out.append("")
        else:
            blank = 0
            out.append(ln.strip())
    return "\n".join(out).strip()


class YargitayClient:
    def __init__(self, session=None):
        self.session = session or requests.Session()
        self.session.headers.update({
            "User-Agent": config.USER_AGENT,
            "Accept": "application/json",
            "Content-Type": "application/json;charset=UTF-8",
        })

    def _istek(self, method: str, url: str, **kw):
        son_hata = None
        for deneme in range(config.MAX_RETRIES):
            try:
                if method == "POST":
                    r = self.session.post(url, timeout=config.TIMEOUT, **kw)
                else:
                    r = self.session.get(url, timeout=config.TIMEOUT, **kw)
                r.raise_for_status()
                return r
            except Exception as e:  # noqa: BLE001
                son_hata = e
                time.sleep(config.REQUEST_DELAY * (2 ** deneme))
        raise YargitayError(f"İstek başarısız: {url} — {son_hata}")

    def ara(self, kelime, arama_tipi="genis", page_size=config.DEFAULT_PAGE_SIZE, page_number=1):
        body = config.arama_govdesi(kelime, arama_tipi, page_size, page_number)
        r = self._istek("POST", config.BASE_URL + config.ARAMA_ENDPOINT, json=body)
        payload = r.json()
        if payload.get("metadata", {}).get("FMTY") != "SUCCESS":
            mesaj = payload.get("metadata", {}).get("FMTE", "Bilinmeyen hata")
            raise YargitayError(f"Arama hatası: {mesaj}")
        data = payload["data"]
        kararlar = [Karar.from_arama(x) for x in (data.get("data") or [])]
        return {"toplam": int(data.get("recordsTotal", 0)), "kararlar": kararlar}

    def ara_topla(self, kelime, adet, arama_tipi="genis", ilerleme_cb=None):
        toplanan, toplam = [], 0
        sayfa = 1
        while len(toplanan) < adet:
            kalan = adet - len(toplanan)
            psize = min(config.DEFAULT_PAGE_SIZE, kalan)
            sonuc = self.ara(kelime, arama_tipi=arama_tipi, page_size=psize, page_number=sayfa)
            toplam = sonuc["toplam"]
            yeni = sonuc["kararlar"]
            if not yeni:
                break
            toplanan.extend(yeni)
            if ilerleme_cb:
                ilerleme_cb(len(toplanan), min(adet, toplam or adet))
            if len(yeni) < psize:
                break
            sayfa += 1
            time.sleep(config.REQUEST_DELAY)
        return {"toplam": toplam, "kararlar": toplanan[:adet]}

    def karar_getir(self, id: str) -> str:
        url = f"{config.BASE_URL}{config.DOKUMAN_ENDPOINT}?id={id}"
        r = self._istek("GET", url)
        payload = r.json()
        return temizle(payload.get("data", ""))
```

- [ ] **Step 4: Testleri çalıştır**

Run: `cd /home/goksel/yargitay_mcp && python3 -m pytest tests/test_client.py -v`
Expected: 5 test PASS.

- [ ] **Step 5: Commit**

```bash
git add -A && git commit -m "feat: YargitayClient (ara/ara_topla/karar_getir) + HTML temizleme"
```

---

### Task 4: Gruplama

**Files:**
- Create: `core/grouping.py`
- Test: `tests/test_grouping.py`

**Interfaces:**
- Produces: `grouping.grupla(kararlar: list, dava_basina: int) -> list[list]` — sırayı koruyarak `dava_basina`'lık dilimler.

- [ ] **Step 1: Failing test — tests/test_grouping.py**

```python
from core.grouping import grupla


def test_tam_bolunme():
    assert len(grupla(list(range(100)), 10)) == 10


def test_eksik_son_grup():
    gruplar = grupla(list(range(23)), 10)
    assert len(gruplar) == 3
    assert len(gruplar[-1]) == 3


def test_bos_liste():
    assert grupla([], 10) == []


def test_sira_korunur():
    assert grupla([1, 2, 3, 4, 5], 2) == [[1, 2], [3, 4], [5]]
```

- [ ] **Step 2: Testi çalıştır, başarısızlığı gör**

Run: `cd /home/goksel/yargitay_mcp && python3 -m pytest tests/test_grouping.py -v`
Expected: FAIL — import hatası.

- [ ] **Step 3: core/grouping.py yaz**

```python
def grupla(kararlar, dava_basina):
    if dava_basina < 1:
        dava_basina = 1
    return [kararlar[i:i + dava_basina] for i in range(0, len(kararlar), dava_basina)]
```

- [ ] **Step 4: Testi çalıştır**

Run: `cd /home/goksel/yargitay_mcp && python3 -m pytest tests/test_grouping.py -v`
Expected: 4 test PASS.

- [ ] **Step 5: Commit**

```bash
git add -A && git commit -m "feat: karar gruplama"
```

---

### Task 5: PDF renderer (fpdf2 garanti + weasyprint opsiyonel)

**Files:**
- Create: `core/renderer.py`
- Test: `tests/test_renderer.py`

**Interfaces:**
- Consumes: `models.Karar`.
- Produces:
  - `renderer.Fpdf2Renderer(font_path=None)` ve `renderer.WeasyPrintRenderer()`, ikisi de `render(kararlar: list[Karar], cikti_yolu: str, baslik: str) -> None` uygular ve dosyayı yazar.
  - `renderer.get_renderer() -> PdfRenderer` — weasyprint kullanılabilirse onu, değilse Fpdf2Renderer döner.
  - `renderer.karar_html(kararlar, baslik) -> str` — WeasyPrint için HTML üretir (ortak biçim).

- [ ] **Step 1: Failing test — tests/test_renderer.py**

```python
from pathlib import Path
from core.models import Karar
from core.renderer import Fpdf2Renderer, get_renderer


def _ornek():
    return [
        Karar(id="1", daire="1. Hukuk Dairesi", esasNo="2025/1", kararNo="2026/2",
              kararTarihi="01.01.2026", arananKelime="kira tespiti",
              metin="Türkçe karar metni: şçğüöı İçtihat.\nİkinci satır."),
        Karar(id="2", daire="3. Hukuk Dairesi", esasNo="2025/5", kararNo="2026/9",
              kararTarihi="02.01.2026", arananKelime="kira tespiti",
              metin="İkinci kararın metni."),
    ]


def test_fpdf2_dosya_uretir(tmp_path):
    yol = tmp_path / "belge_01.pdf"
    Fpdf2Renderer().render(_ornek(), str(yol), 'Arama: "kira tespiti" (Belge 1/1)')
    assert yol.exists()
    assert yol.stat().st_size > 1000
    assert yol.read_bytes()[:4] == b"%PDF"


def test_get_renderer_render_calisir(tmp_path):
    yol = tmp_path / "b.pdf"
    get_renderer().render(_ornek(), str(yol), "Başlık")
    assert yol.exists() and yol.stat().st_size > 500
```

- [ ] **Step 2: Testi çalıştır, başarısızlığı gör**

Run: `cd /home/goksel/yargitay_mcp && python3 -m pytest tests/test_renderer.py -v`
Expected: FAIL — import hatası.

- [ ] **Step 3: core/renderer.py yaz**

```python
import html as _html
from pathlib import Path

_DEJAVU_ADAYLARI = [
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "/usr/share/fonts/dejavu/DejaVuSans.ttf",
    "/usr/share/fonts/TTF/DejaVuSans.ttf",
]


def _dejavu_bul():
    for p in _DEJAVU_ADAYLARI:
        if Path(p).exists():
            return p
    return None


def _karar_basligi(k, sira, toplam):
    return (f"Dava {sira}/{toplam}\n{k.daire}   {k.esasNo} E.  /  {k.kararNo} K."
            f"\nKarar Tarihi: {k.kararTarihi}")


class Fpdf2Renderer:
    def __init__(self, font_path=None):
        self.font_path = font_path or _dejavu_bul()

    def render(self, kararlar, cikti_yolu, baslik):
        from fpdf import FPDF
        pdf = FPDF()
        pdf.set_auto_page_break(True, margin=15)
        if self.font_path:
            pdf.add_font("Doc", "", self.font_path)
            pdf.add_font("Doc", "B", self.font_path)
            aile = "Doc"
        else:
            aile = "Helvetica"  # DejaVu yoksa (Türkçe glifleri sınırlı) son çare
        pdf.add_page()
        pdf.set_font(aile, "B", 14)
        pdf.multi_cell(0, 8, baslik)
        pdf.ln(2)
        n = len(kararlar)
        for i, k in enumerate(kararlar, 1):
            pdf.ln(3)
            pdf.set_font(aile, "B", 11)
            pdf.multi_cell(0, 6, _karar_basligi(k, i, n))
            pdf.set_font(aile, "", 10)
            metin = k.metin if aile == "Doc" else k.metin.encode("latin-1", "replace").decode("latin-1")
            pdf.multi_cell(0, 5, metin or "(metin alınamadı)")
        pdf.output(cikti_yolu)


def karar_html(kararlar, baslik):
    n = len(kararlar)
    parcalar = [
        "<html><head><meta charset='utf-8'><style>",
        "body{font-family:DejaVu Sans,Arial,sans-serif;font-size:11px;line-height:1.4;}",
        "h1{font-size:15px;} .k{margin-top:18px;} .b{font-weight:bold;white-space:pre-line;}",
        ".m{white-space:pre-wrap;margin-top:6px;}</style></head><body>",
        f"<h1>{_html.escape(baslik)}</h1>",
    ]
    for i, k in enumerate(kararlar, 1):
        parcalar.append("<div class='k'>")
        parcalar.append(f"<div class='b'>{_html.escape(_karar_basligi(k, i, n))}</div>")
        parcalar.append(f"<div class='m'>{_html.escape(k.metin or '(metin alınamadı)')}</div>")
        parcalar.append("</div>")
    parcalar.append("</body></html>")
    return "".join(parcalar)


class WeasyPrintRenderer:
    def render(self, kararlar, cikti_yolu, baslik):
        from weasyprint import HTML
        HTML(string=karar_html(kararlar, baslik)).write_pdf(cikti_yolu)


def get_renderer():
    try:
        from weasyprint import HTML  # noqa: F401
        return WeasyPrintRenderer()
    except Exception:
        return Fpdf2Renderer()
```

- [ ] **Step 4: Testi çalıştır**

Run: `cd /home/goksel/yargitay_mcp && python3 -m pytest tests/test_renderer.py -v`
Expected: 2 test PASS. (DejaVu yoksa test yine geçer; `-s` ile uyarı görülebilir.)

- [ ] **Step 5: Commit**

```bash
git add -A && git commit -m "feat: PDF renderer — fpdf2 garanti + weasyprint opsiyonel"
```

---

### Task 6: Pipeline (collect_and_build)

**Files:**
- Create: `core/pipeline.py`
- Test: `tests/test_pipeline.py`

**Interfaces:**
- Consumes: `client.YargitayClient`, `renderer.get_renderer`, `grouping.grupla`, `config`.
- Produces:
  - `pipeline.collect_and_build(kelime, adet, arama_tipi="genis", dava_basina=10, ilerleme_cb=None, output_dir=None, client=None, renderer=None) -> dict`
  - Dönen özet (aynı zamanda `ozet.json` olarak yazılır):
    ```
    {"arama","arama_tipi","istenen","bulunabilir_toplam","toplanan",
     "atlanan","dava_basina","belge_sayisi","eksik_uyarisi","belgeler",
     "klasor","tarih"}
    ```

- [ ] **Step 1: Failing test — tests/test_pipeline.py**

```python
import json
from pathlib import Path
from unittest.mock import MagicMock
from core.models import Karar
from core import pipeline


def _sahte_client(toplam, adet_bulunan):
    c = MagicMock()
    kararlar = [Karar(id=str(i), daire="1. Hukuk Dairesi", esasNo=f"2025/{i}",
                      kararNo=f"2026/{i}", kararTarihi="01.01.2026",
                      arananKelime="x") for i in range(adet_bulunan)]
    c.ara_topla.return_value = {"toplam": toplam, "kararlar": kararlar}
    c.karar_getir.side_effect = lambda _id: f"metin-{_id}"
    return c


class _SahteRenderer:
    def __init__(self):
        self.cagrilar = []
    def render(self, kararlar, cikti_yolu, baslik):
        self.cagrilar.append(len(kararlar))
        Path(cikti_yolu).write_bytes(b"%PDF-1.4 sahte")


def test_tam_100_10_belge(tmp_path):
    c = _sahte_client(toplam=5000, adet_bulunan=100)
    r = _SahteRenderer()
    ozet = pipeline.collect_and_build("kira", 100, dava_basina=10,
                                      output_dir=tmp_path, client=c, renderer=r)
    assert ozet["toplanan"] == 100
    assert ozet["belge_sayisi"] == 10
    assert ozet["eksik_uyarisi"] is None
    assert len(list(Path(ozet["klasor"]).glob("belge_*.pdf"))) == 10
    assert (Path(ozet["klasor"]) / "ozet.json").exists()


def test_eksik_sonuc_uyarisi(tmp_path):
    c = _sahte_client(toplam=20, adet_bulunan=20)
    ozet = pipeline.collect_and_build("nadir", 100, dava_basina=10,
                                      output_dir=tmp_path, client=c, renderer=_SahteRenderer())
    assert ozet["istenen"] == 100
    assert ozet["toplanan"] == 20
    assert ozet["belge_sayisi"] == 2
    assert ozet["eksik_uyarisi"] and "100" in ozet["eksik_uyarisi"] and "20" in ozet["eksik_uyarisi"]


def test_atlanan_karar_cokmez(tmp_path):
    c = _sahte_client(toplam=30, adet_bulunan=5)
    def bazen_hata(_id):
        if _id == "2":
            raise RuntimeError("indirilemedi")
        return f"metin-{_id}"
    c.karar_getir.side_effect = bazen_hata
    ozet = pipeline.collect_and_build("x", 5, dava_basina=10,
                                      output_dir=tmp_path, client=c, renderer=_SahteRenderer())
    assert ozet["atlanan"] == 1
    assert ozet["toplanan"] == 4  # metni alınan
    assert ozet["belge_sayisi"] == 1
```

- [ ] **Step 2: Testi çalıştır, başarısızlığı gör**

Run: `cd /home/goksel/yargitay_mcp && python3 -m pytest tests/test_pipeline.py -v`
Expected: FAIL — import hatası.

- [ ] **Step 3: core/pipeline.py yaz**

```python
import json
from pathlib import Path

from . import config
from .client import YargitayClient
from .grouping import grupla
from .renderer import get_renderer


def collect_and_build(kelime, adet, arama_tipi="genis", dava_basina=None,
                      ilerleme_cb=None, output_dir=None, client=None, renderer=None):
    dava_basina = dava_basina or config.DEFAULT_DAVA_BASINA
    client = client or YargitayClient()
    renderer = renderer or get_renderer()
    output_dir = Path(output_dir) if output_dir else config.OUTPUT_DIR

    sonuc = client.ara_topla(kelime, adet, arama_tipi=arama_tipi)
    aday = sonuc["kararlar"]
    bulunabilir_toplam = sonuc["toplam"]
    hedef = len(aday)

    doldu, atlanan = [], 0
    for i, k in enumerate(aday):
        try:
            k.metin = client.karar_getir(k.id)
            doldu.append(k)
        except Exception:  # noqa: BLE001
            atlanan += 1
        if ilerleme_cb:
            ilerleme_cb(i + 1, hedef)

    gruplar = grupla(doldu, dava_basina)
    klasor = output_dir / config.slug(kelime) / config.timestamp()
    klasor.mkdir(parents=True, exist_ok=True)

    belgeler = []
    for idx, g in enumerate(gruplar, 1):
        ad = f"belge_{idx:02d}.pdf"
        baslik = f'Arama: "{kelime}"   (Belge {idx}/{len(gruplar)})'
        renderer.render(g, str(klasor / ad), baslik)
        belgeler.append(ad)

    eksik = None
    if len(doldu) < adet:
        eksik = f"{adet} dava istendi, {len(doldu)} dava bulundu/işlendi."

    ozet = {
        "arama": kelime,
        "arama_tipi": arama_tipi,
        "istenen": adet,
        "bulunabilir_toplam": bulunabilir_toplam,
        "toplanan": len(doldu),
        "atlanan": atlanan,
        "dava_basina": dava_basina,
        "belge_sayisi": len(belgeler),
        "eksik_uyarisi": eksik,
        "belgeler": belgeler,
        "klasor": str(klasor),
        "tarih": config.timestamp(),
    }
    (klasor / "ozet.json").write_text(
        json.dumps(ozet, ensure_ascii=False, indent=2), encoding="utf-8")
    return ozet
```

- [ ] **Step 4: Testi çalıştır**

Run: `cd /home/goksel/yargitay_mcp && python3 -m pytest tests/test_pipeline.py -v`
Expected: 3 test PASS.

- [ ] **Step 5: Tüm birim testleri çalıştır**

Run: `cd /home/goksel/yargitay_mcp && python3 -m pytest -v`
Expected: tüm testler PASS (integration atlanır).

- [ ] **Step 6: Commit**

```bash
git add -A && git commit -m "feat: collect_and_build pipeline + eksik-sonuç raporlama"
```

---

### Task 7: MCP sunucusu

**Files:**
- Create: `mcp_server.py`

**Interfaces:**
- Consumes: `core.pipeline.collect_and_build`, `core.client.YargitayClient`.
- Produces: FastMCP stdio sunucusu; araçlar `yargitay_ara`, `yargitay_belge_uret`, `yargitay_karar_getir`.

- [ ] **Step 1: mcp_server.py yaz**

```python
"""Yargıtay karar arama MCP sunucusu (stdio)."""
from mcp.server.fastmcp import FastMCP

from core.client import YargitayClient
from core.pipeline import collect_and_build

mcp = FastMCP("yargitay")


@mcp.tool()
def yargitay_ara(kelime: str, adet: int = 10, arama_tipi: str = "genis") -> dict:
    """Yargıtay kararlarını arar (PDF üretmez, sadece liste).

    arama_tipi: "genis" (kelimeler geçen tüm kararlar) veya "tam" (birebir ifade).
    Döner: {"bulunabilir_toplam": int, "kararlar": [{id,daire,esasNo,kararNo,kararTarihi}]}
    """
    c = YargitayClient()
    sonuc = c.ara_topla(kelime, adet, arama_tipi=arama_tipi)
    return {
        "bulunabilir_toplam": sonuc["toplam"],
        "kararlar": [
            {"id": k.id, "daire": k.daire, "esasNo": k.esasNo,
             "kararNo": k.kararNo, "kararTarihi": k.kararTarihi}
            for k in sonuc["kararlar"]
        ],
    }


@mcp.tool()
def yargitay_belge_uret(kelime: str, adet: int = 10, arama_tipi: str = "genis",
                        dava_basina: int = 10) -> dict:
    """Kararları toplar, her `dava_basina` kararı 1 PDF yapar ve özet döner.

    İstenen adetten az bulunursa hata değildir; özetteki `eksik_uyarisi` bunu belirtir.
    Döner: ozet.json içeriği (klasor, belgeler, istenen/toplanan/belge_sayisi, eksik_uyarisi).
    """
    return collect_and_build(kelime, adet, arama_tipi=arama_tipi, dava_basina=dava_basina)


@mcp.tool()
def yargitay_karar_getir(id: str) -> str:
    """Tek bir kararın temizlenmiş tam metnini döner."""
    return YargitayClient().karar_getir(id)


if __name__ == "__main__":
    mcp.run()
```

- [ ] **Step 2: Sunucunun hatasız başladığını doğrula (import + kısa açılış)**

Run: `cd /home/goksel/yargitay_mcp && python3 -c "import mcp_server; print('MCP araçları hazır:', [t.name for t in mcp_server.mcp._tool_manager.list_tools()])"`
Expected: `MCP araçları hazır: ['yargitay_ara', 'yargitay_belge_uret', 'yargitay_karar_getir']`
(Not: FastMCP iç API adı sürüme göre `_tool_manager.list_tools()` farklı olabilir; hata verirse sadece `import mcp_server` başarılı olması yeterlidir — bunu doğrula: `python3 -c "import mcp_server; print('ok')"`.)

- [ ] **Step 3: Commit**

```bash
git add -A && git commit -m "feat: MCP sunucusu (ara/belge_uret/karar_getir)"
```

---

### Task 8: Web arayüzü (FastAPI + tek sayfa)

**Files:**
- Create: `web/app.py`, `web/static/index.html`, `web/static/app.js`, `web/static/style.css`, `web/__init__.py`

**Interfaces:**
- Consumes: `core.pipeline.collect_and_build`.
- Produces: FastAPI `app`; uçlar `POST /ara`, `GET /durum/{job_id}`, `GET /indir/{job_id}/{dosya}`, `GET /` (statik arayüz). Bellek-içi `JOBS` sözlüğü iş durumunu tutar.

- [ ] **Step 1: web/app.py yaz**

```python
import threading
import uuid
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from core.pipeline import collect_and_build

app = FastAPI(title="Yargıtay Karar Toplayıcı")
STATIC = Path(__file__).parent / "static"

JOBS = {}  # job_id -> {durum, indirilen, hedef, ozet, hata}


class AramaIstegi(BaseModel):
    kelime: str
    adet: int = 10
    arama_tipi: str = "genis"
    dava_basina: int = 10


def _calistir(job_id, istek: AramaIstegi):
    def cb(indirilen, hedef):
        JOBS[job_id]["indirilen"] = indirilen
        JOBS[job_id]["hedef"] = hedef
    try:
        JOBS[job_id]["durum"] = "calisiyor"
        ozet = collect_and_build(
            istek.kelime, istek.adet, arama_tipi=istek.arama_tipi,
            dava_basina=istek.dava_basina, ilerleme_cb=cb)
        JOBS[job_id]["ozet"] = ozet
        JOBS[job_id]["durum"] = "bitti"
    except Exception as e:  # noqa: BLE001
        JOBS[job_id]["hata"] = str(e)
        JOBS[job_id]["durum"] = "hata"


@app.post("/ara")
def ara(istek: AramaIstegi):
    job_id = uuid.uuid4().hex
    JOBS[job_id] = {"durum": "basladi", "indirilen": 0, "hedef": istek.adet,
                    "ozet": None, "hata": None}
    threading.Thread(target=_calistir, args=(job_id, istek), daemon=True).start()
    return {"job_id": job_id}


@app.get("/durum/{job_id}")
def durum(job_id: str):
    j = JOBS.get(job_id)
    if not j:
        return JSONResponse({"hata": "iş bulunamadı"}, status_code=404)
    return j


@app.get("/indir/{job_id}/{dosya}")
def indir(job_id: str, dosya: str):
    j = JOBS.get(job_id)
    if not j or not j.get("ozet"):
        return JSONResponse({"hata": "hazır değil"}, status_code=404)
    # yol güvenliği: sadece dosya adı, klasör dışına çıkışı engelle
    if "/" in dosya or ".." in dosya:
        return JSONResponse({"hata": "geçersiz dosya"}, status_code=400)
    yol = Path(j["ozet"]["klasor"]) / dosya
    if not yol.exists():
        return JSONResponse({"hata": "dosya yok"}, status_code=404)
    return FileResponse(str(yol), media_type="application/pdf", filename=dosya)


app.mount("/", StaticFiles(directory=str(STATIC), html=True), name="static")
```

- [ ] **Step 2: web/__init__.py (boş) ve web/static/index.html yaz**

`web/__init__.py`: boş dosya.

`web/static/index.html`:
```html
<!DOCTYPE html>
<html lang="tr">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Yargıtay Karar Toplayıcı</title>
  <link rel="stylesheet" href="/style.css">
</head>
<body>
  <main>
    <h1>Yargıtay Karar Toplayıcı</h1>
    <p class="alt">Arama kelimesi gir, kaç dava istediğini seç. Her 10 dava 1 PDF olur.</p>
    <form id="form">
      <label>Arama kelimesi
        <input id="kelime" required placeholder="ör. kira tespiti">
      </label>
      <label>Kaç dava
        <input id="adet" type="number" min="1" max="1000" value="10">
      </label>
      <fieldset>
        <legend>Arama tipi</legend>
        <label class="satir"><input type="radio" name="tip" value="genis" checked> Geniş arama</label>
        <label class="satir"><input type="radio" name="tip" value="tam"> Tam ifade</label>
      </fieldset>
      <label>Belge başına dava
        <input id="dava_basina" type="number" min="1" max="50" value="10">
      </label>
      <button type="submit" id="btn">Başlat</button>
    </form>

    <section id="ilerleme" hidden>
      <div class="bar"><div id="dolgu"></div></div>
      <p id="ilerleme-metin">Hazırlanıyor…</p>
    </section>

    <section id="sonuc" hidden>
      <p id="ozet-metin"></p>
      <ul id="belgeler"></ul>
    </section>

    <p id="hata" class="hata" hidden></p>
  </main>
  <script src="/app.js"></script>
</body>
</html>
```

- [ ] **Step 3: web/static/app.js yaz**

```javascript
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
```

- [ ] **Step 4: web/static/style.css yaz**

```css
:root { --ink:#1e293b; --muted:#64748b; --accent:#0e7490; --bg:#f8fafc; --line:#e2e8f0; }
* { box-sizing: border-box; }
body { margin:0; background:var(--bg); color:var(--ink);
  font-family:system-ui,-apple-system,Segoe UI,Roboto,sans-serif; }
main { max-width:640px; margin:40px auto; padding:0 20px; }
h1 { font-size:1.6rem; margin-bottom:4px; }
.alt { color:var(--muted); margin-top:0; }
form { display:flex; flex-direction:column; gap:14px; background:#fff;
  padding:22px; border:1px solid var(--line); border-radius:12px; }
label { display:flex; flex-direction:column; gap:6px; font-weight:600; font-size:.92rem; }
input[type=text], input[type=number], input:not([type]) {
  padding:10px; border:1px solid var(--line); border-radius:8px; font-size:1rem; }
fieldset { border:1px solid var(--line); border-radius:8px; }
.satir { flex-direction:row; align-items:center; gap:8px; font-weight:500; }
button { padding:12px; background:var(--accent); color:#fff; border:none;
  border-radius:8px; font-size:1rem; font-weight:600; cursor:pointer; }
button:disabled { opacity:.6; cursor:not-allowed; }
section { margin-top:22px; background:#fff; padding:18px; border:1px solid var(--line);
  border-radius:12px; }
.bar { height:14px; background:var(--line); border-radius:7px; overflow:hidden; }
#dolgu { height:100%; width:0; background:var(--accent); transition:width .3s; }
#belgeler { list-style:none; padding:0; }
#belgeler li a { display:inline-block; margin:4px 0; color:var(--accent);
  text-decoration:none; font-weight:600; }
.hata { color:#b91c1c; font-weight:600; }
```

- [ ] **Step 5: Sunucuyu başlat ve arayüzü doğrula**

```bash
cd /home/goksel/yargitay_mcp
python3 -m uvicorn web.app:app --host 127.0.0.1 --port 8477 &
sleep 3
curl -s -o /dev/null -w "anasayfa:%{http_code}\n" http://127.0.0.1:8477/
curl -s -X POST http://127.0.0.1:8477/ara -H 'Content-Type: application/json' \
  --data '{"kelime":"kira tespiti","adet":3,"arama_tipi":"genis","dava_basina":10}'
```
Expected: `anasayfa:200` ve `{"job_id":"..."}`. Birkaç saniye sonra `curl http://127.0.0.1:8477/durum/<job_id>` `durum:"bitti"` ve 1 belge göstermeli. Sonra sunucuyu durdur: `kill %1`.
(Not: arka plan süreci başlatma bu ortamda engelliyse, kullanıcıya tek satır komut ver: `python3 -m uvicorn web.app:app --port 8477` ve tarayıcıdan `http://127.0.0.1:8477` aç.)

- [ ] **Step 6: Commit**

```bash
git add -A && git commit -m "feat: web arayüzü — arama formu, ilerleme, PDF indirme"
```

---

### Task 9: Entegrasyon testi + README

**Files:**
- Create: `tests/test_integration.py`, `README.md`

**Interfaces:**
- Consumes: tüm çekirdek.
- Produces: gerçek API'ye vuran işaretli test + kullanım dokümanı.

- [ ] **Step 1: tests/test_integration.py yaz**

```python
import pytest
from core.client import YargitayClient
from core import pipeline


@pytest.mark.integration
def test_gercek_arama_ve_belge(tmp_path):
    ozet = pipeline.collect_and_build("kira tespiti", adet=3, dava_basina=10,
                                      output_dir=tmp_path)
    assert ozet["toplanan"] >= 1
    assert ozet["belge_sayisi"] == 1
    pdfs = list((tmp_path).rglob("belge_*.pdf"))
    assert pdfs and pdfs[0].stat().st_size > 1000


@pytest.mark.integration
def test_gercek_karar_getir():
    c = YargitayClient()
    sonuc = c.ara("kira tespiti", page_size=1)
    metin = c.karar_getir(sonuc["kararlar"][0].id)
    assert len(metin) > 100
```

- [ ] **Step 2: Entegrasyon testini bir kez gerçek API ile çalıştır**

Run: `cd /home/goksel/yargitay_mcp && python3 -m pytest -m integration -v`
Expected: 2 test PASS (ağ gerektirir). Üretilen PDF'i elle aç ve Türkçe karakterlerin doğru göründüğünü teyit et.

- [ ] **Step 3: README.md yaz**

```markdown
# Yargıtay Karar Toplayıcı

`karararama.yargitay.gov.tr`'den arama kelimesiyle Yargıtay kararlarını toplar,
her 10 kararı 1 PDF belgesi yapar. Web arayüzü + MCP sunucusu.

## Kurulum
    python3 -m pip install -r requirements.txt
    # (opsiyonel, daha kaliteli PDF): python3 -m pip install -r requirements-optional.txt

## Web arayüzü
    python3 -m uvicorn web.app:app --port 8477
Tarayıcıdan http://127.0.0.1:8477 → kelime + dava sayısı gir, Başlat.
Belgeler `output/<arama>/<tarih>/belge_01.pdf …` altına yazılır.

## MCP (Claude'a ekleme)
    {"mcpServers":{"yargitay":{"command":"python3","args":["/home/goksel/yargitay_mcp/mcp_server.py"]}}}
Araçlar: `yargitay_ara`, `yargitay_belge_uret`, `yargitay_karar_getir`.

## Notlar
- İstenen dava sayısından az bulunması hata değildir; özet ve arayüz farkı bildirir.
- Test: `python3 -m pytest` (birim), `python3 -m pytest -m integration` (gerçek API).
```

- [ ] **Step 4: Commit**

```bash
git add -A && git commit -m "test: entegrasyon testleri + README"
```

---

## Self-Review Notu (plan yazarı tarafından kontrol edildi)

- **Spec kapsamı:** arama (Task 3), 10'arlı gruplama (Task 4), PDF (Task 5), pipeline+eksik-raporlama (Task 6), MCP (Task 7), web arayüzü+ilerleme+indirme (Task 8), arama tipi seçimi (config Task 1 + client Task 3 + UI Task 8) — hepsi karşılanıyor.
- **Placeholder yok:** her kod adımı tam içerik içerir.
- **Tip tutarlılığı:** `collect_and_build` özet anahtarları (`klasor`, `belgeler`, `toplanan`, `eksik_uyarisi`) web (Task 8) ve MCP (Task 7) tüketicileriyle eşleşir; `ara_topla`/`karar_getir` imzaları client ile pipeline arasında tutarlı.
- **Spec sapması:** daire filtresi v1'de çıkarıldı (Global Constraints'te belirtildi; spec §10 zaten "sonraki sürüm" demişti) — MCP/UI imzaları buna göre sadeleştirildi.
