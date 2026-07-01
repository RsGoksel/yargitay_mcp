import pytest
from unittest.mock import MagicMock
from core.client import YargitayClient, YargitayError, temizle


def _fake_session(json_payloads):
    """Her POST/GET çağrısında sıradaki payload'ı döndüren sahte session."""
    session = MagicMock()
    resp_list = []
    for p in json_payloads:
        r = MagicMock()
        r.status_code = 200
        r.json.return_value = p
        r.raise_for_status.return_value = None
        resp_list.append(r)
    session.post.side_effect = resp_list
    session.get.side_effect = resp_list
    return session


def test_temizle_br_ve_etiket(arama_yaniti):
    html = '<html><body><b>Başlık</b><br>Satır1<br>Satır2</body></html>'
    metin = temizle(html)
    assert "Başlık" in metin
    assert "Satır1\nSatır2" in metin
    assert "<" not in metin


def test_ara_parse(arama_yaniti):
    client = YargitayClient(session=_fake_session([arama_yaniti]))
    sonuc = client.ara("kira tespiti")
    assert sonuc["toplam"] == arama_yaniti["data"]["recordsTotal"]
    assert len(sonuc["kararlar"]) == len(arama_yaniti["data"]["data"])
    assert sonuc["kararlar"][0].id == str(arama_yaniti["data"]["data"][0]["id"])


def test_ara_hata_metadata():
    hatali = {"data": None, "metadata": {"FMTY": "ERROR", "FMTE": "Hata Oluştu!"}}
    client = YargitayClient(session=_fake_session([hatali]))
    with pytest.raises(YargitayError):
        client.ara("x")


def test_tam_ifade_tirnaklar(arama_yaniti):
    client = YargitayClient(session=_fake_session([arama_yaniti]))
    captured = {}
    orig = client.session.post

    def spy(url, **kw):
        captured["body"] = kw.get("json")
        return orig(url, **kw)

    client.session.post = spy
    client.ara("kira tespiti", arama_tipi="tam")
    assert captured["body"]["data"]["arananKelime"] == '"kira tespiti"'


def _sayfalama_sahte_session(kararlar_havuzu, toplam):
    """Gerçek API gibi davranır: gönderilen pageSize/pageNumber'a göre
    havuzdan doğru dilimi döner (doğrulanmış davranış: sunucu pageSize'ı
    birebir uygular)."""
    session = MagicMock()

    def post(url, json=None, **kw):
        page_number = json["data"]["pageNumber"]
        page_size = json["data"]["pageSize"]
        start = (page_number - 1) * page_size
        dilim = kararlar_havuzu[start:start + page_size]
        payload = {
            "data": {"data": dilim, "recordsTotal": toplam, "recordsFiltered": toplam},
            "metadata": {"FMTY": "SUCCESS"},
        }
        r = MagicMock()
        r.status_code = 200
        r.json.return_value = payload
        r.raise_for_status.return_value = None
        return r

    session.post.side_effect = post
    return session


def test_ara_topla_sayfalama(arama_yaniti):
    # DEFAULT_PAGE_SIZE=100; 130 kayıtlık havuzdan 120 istenirse iki sayfada
    # (100 + 20) toplanıp 120 döner.
    sablon = arama_yaniti["data"]["data"][0]
    havuz = [dict(sablon, id=str(i)) for i in range(130)]
    client = YargitayClient(session=_sayfalama_sahte_session(havuz, toplam=len(havuz)))
    sonuc = client.ara_topla("kira", adet=120, arama_tipi="genis")
    assert len(sonuc["kararlar"]) == 120
    assert [k.id for k in sonuc["kararlar"]] == [str(i) for i in range(120)]


def test_karar_getir_temizlenmis_metin_doner(dokuman_yaniti):
    client = YargitayClient(session=_fake_session([dokuman_yaniti]))
    metin = client.karar_getir("1213744300")
    assert "<" not in metin
    assert len(metin) > 20
