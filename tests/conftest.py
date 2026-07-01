import json
from pathlib import Path
import pytest

FIX = Path(__file__).parent / "fixtures"


@pytest.fixture
def arama_yaniti():
    return json.loads((FIX / "arama.json").read_text(encoding="utf-8"))


@pytest.fixture
def dokuman_yaniti():
    return json.loads((FIX / "dokuman.json").read_text(encoding="utf-8"))
