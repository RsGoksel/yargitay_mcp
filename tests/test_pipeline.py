import json
from pathlib import Path
from unittest.mock import MagicMock
import pytest
from core.models import Karar
from core import pipeline, config


@pytest.fixture(autouse=True)
def _no_real_sleep(monkeypatch):
    # Testler gerçek time.sleep ile bekletilmesin (birim testleri hızlı kalsın);
    # gecikme davranışını doğrulayan test kendi casusunu ayrıca kurar.
    monkeypatch.setattr(pipeline.time, "sleep", lambda s: None)


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


def test_karar_indirmeleri_arasinda_gecikme_var(tmp_path, monkeypatch):
    # Kök neden: getDokuman art arda beklemesiz çağrılınca sunucu 429 (Too Many
    # Requests) döndürüyor (gerçek API'de doğrulandı). Her indirme arasında
    # REQUEST_DELAY kadar beklenmeli — ara_topla()'nın sayfalar arası zaten
    # yaptığı gibi.
    bekletmeler = []
    monkeypatch.setattr(pipeline.time, "sleep", lambda s: bekletmeler.append(s))
    c = _sahte_client(toplam=3, adet_bulunan=3)
    pipeline.collect_and_build("x", 3, dava_basina=10, output_dir=tmp_path,
                                client=c, renderer=_SahteRenderer())
    assert bekletmeler == [config.REQUEST_DELAY, config.REQUEST_DELAY]
