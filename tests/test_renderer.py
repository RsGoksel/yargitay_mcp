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
