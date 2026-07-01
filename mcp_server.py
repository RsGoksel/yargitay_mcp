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
