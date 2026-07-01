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
