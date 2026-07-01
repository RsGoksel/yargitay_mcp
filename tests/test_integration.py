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
