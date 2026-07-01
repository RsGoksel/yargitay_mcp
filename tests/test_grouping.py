from core.grouping import grupla


def test_tam_bolunme():
    assert len(grupla(list(range(100)), 10)) == 10


def test_eksik_son_grup():
    gruplar = grupla(list(range(23)), 10)
    assert len(gruplar) == 3
    assert len(gruplar[-1]) == 3


def test_bos_liste():
    assert grupla([], 10) == []


def test_sira_korunur():
    assert grupla([1, 2, 3, 4, 5], 2) == [[1, 2], [3, 4], [5]]
