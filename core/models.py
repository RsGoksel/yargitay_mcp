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
