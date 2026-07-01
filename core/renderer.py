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
        pdf.multi_cell(0, 8, baslik, new_x="LMARGIN", new_y="NEXT")
        pdf.ln(2)
        n = len(kararlar)
        for i, k in enumerate(kararlar, 1):
            pdf.ln(3)
            pdf.set_font(aile, "B", 11)
            pdf.multi_cell(0, 6, _karar_basligi(k, i, n), new_x="LMARGIN", new_y="NEXT")
            pdf.set_font(aile, "", 10)
            metin = k.metin if aile == "Doc" else k.metin.encode("latin-1", "replace").decode("latin-1")
            pdf.multi_cell(0, 5, metin or "(metin alınamadı)", new_x="LMARGIN", new_y="NEXT")
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
