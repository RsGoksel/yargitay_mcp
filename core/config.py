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
