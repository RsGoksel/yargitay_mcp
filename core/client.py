import time
import requests
from bs4 import BeautifulSoup

from . import config
from .models import Karar


class YargitayError(Exception):
    pass


class YargitayCaptchaError(YargitayError):
    """Site otomatik erişimi tespit edip CAPTCHA istiyor; hemen tekrar
    denemek durumu düzeltmez, bir süre beklemek gerekir."""
    pass


def temizle(html: str) -> str:
    soup = BeautifulSoup(html or "", "html.parser")
    for br in soup.find_all("br"):
        br.replace_with("\n")
    text = soup.get_text().replace("\t", " ")
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
        # Enjekte edilen (test) session'lar zaten hazır kabul edilir; gerçek
        # requests.Session kullanıldığında ilk istekten önce oturum ısıtılır.
        self._oturum_hazir = session is not None

    def _oturum_hazirla(self):
        """Site bir WAF çerezi (TS01...) bekliyor; önce anasayfayı ziyaret
        etmeden arama istekleri metadata.FMTY == "ERROR" döner."""
        if self._oturum_hazir:
            return
        try:
            self.session.get(config.BASE_URL + "/", timeout=config.TIMEOUT)
        except Exception:  # noqa: BLE001
            pass
        self._oturum_hazir = True

    def _istek(self, method: str, url: str, **kw):
        self._oturum_hazirla()
        son_hata = None
        for deneme in range(config.MAX_RETRIES):
            try:
                if method == "POST":
                    r = self.session.post(url, timeout=config.TIMEOUT, **kw)
                else:
                    r = self.session.get(url, timeout=config.TIMEOUT, **kw)
                if r.status_code == 429:
                    # Sunucu "çok hızlı gidiyorsun" diyor (gerçek API'de
                    # doğrulandı); genel hata backoff'undan daha uzun bekle,
                    # varsa Retry-After'a uy.
                    bekleme = config.RATE_LIMIT_BACKOFF
                    try:
                        bekleme = float(r.headers.get("Retry-After", bekleme))
                    except (TypeError, ValueError):
                        pass
                    son_hata = f"429 Too Many Requests (bekleme: {bekleme}s)"
                    time.sleep(bekleme)
                    continue
                r.raise_for_status()
                return r
            except Exception as e:  # noqa: BLE001
                son_hata = e
                time.sleep(config.REQUEST_DELAY * (2 ** deneme))
        raise YargitayError(f"İstek başarısız: {url} — {son_hata}")

    def ara(self, kelime, arama_tipi="genis", page_size=config.DEFAULT_PAGE_SIZE, page_number=1):
        body = config.arama_govdesi(kelime, arama_tipi, page_size, page_number)
        son_mesaj = "Bilinmeyen hata"
        for deneme in range(config.MAX_RETRIES):
            r = self._istek("POST", config.BASE_URL + config.ARAMA_ENDPOINT, json=body)
            payload = r.json()
            if payload.get("metadata", {}).get("FMTY") == "SUCCESS":
                data = payload["data"]
                kararlar = [Karar.from_arama(x) for x in (data.get("data") or [])]
                return {"toplam": int(data.get("recordsTotal", 0)), "kararlar": kararlar}
            son_mesaj = payload.get("metadata", {}).get("FMTE", "Bilinmeyen hata")
            if "displaycaptcha" in son_mesaj.lower():
                # Tekrar denemek yardımcı olmaz (WAF bot tespiti); hemen bildir.
                raise YargitayCaptchaError(
                    "Yargıtay sitesi otomatik erişimi tespit edip CAPTCHA istiyor. "
                    "Bir süre bekleyip tekrar deneyin (çok sık/hızlı istek göndermekten kaçının)."
                )
            # WAF çerezi geçici olarak reddedilmiş olabilir (gözlemlenen ara
            # sıra davranış); sonraki denemeden önce oturumu yeniden ısıt.
            self._oturum_hazir = False
            if deneme < config.MAX_RETRIES - 1:
                time.sleep(config.REQUEST_DELAY * (2 ** deneme))
        raise YargitayError(f"Arama hatası: {son_mesaj}")

    def ara_topla(self, kelime, adet, arama_tipi="genis", ilerleme_cb=None):
        # Sunucu ofseti (pageNumber-1)*pageSize ile hesaplar; sayfalar arası
        # pageSize sabit tutulmalı, yoksa sonraki sayfalar kayar/çakışır.
        toplanan, toplam = [], 0
        sayfa = 1
        page_size = config.DEFAULT_PAGE_SIZE
        while len(toplanan) < adet:
            sonuc = self.ara(kelime, arama_tipi=arama_tipi, page_size=page_size, page_number=sayfa)
            toplam = sonuc["toplam"]
            yeni = sonuc["kararlar"]
            if not yeni:
                break
            toplanan.extend(yeni)
            if ilerleme_cb:
                ilerleme_cb(min(len(toplanan), adet), min(adet, toplam or adet))
            if len(yeni) < page_size:
                break
            sayfa += 1
            time.sleep(config.REQUEST_DELAY)
        return {"toplam": toplam, "kararlar": toplanan[:adet]}

    def karar_getir(self, id: str) -> str:
        url = f"{config.BASE_URL}{config.DOKUMAN_ENDPOINT}?id={id}"
        r = self._istek("GET", url)
        payload = r.json()
        return temizle(payload.get("data", ""))
