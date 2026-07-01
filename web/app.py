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
