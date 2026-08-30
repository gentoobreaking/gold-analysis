"""
T056 - get_sentiment_data 不再回傳假情緒

驗證：
- 真實來源可用時回傳 available=True 與真實 fear_greed_index
- 來源失敗時回傳 available=False（而非假 "Greed"）
"""

import asyncio
import json
import os
import sys
from unittest.mock import patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.tools.data_tools import DataTools


def _fake_payload():
    return json.dumps({"data": [{"value": "72", "value_classification": "Greed"}]}).encode()


def test_real_source_available():
    dt = DataTools()
    with patch("app.tools.data_tools.urllib.request.urlopen") as urlopen:
        urlopen.return_value.__enter__.return_value.read.return_value = _fake_payload()
        out = asyncio.run(dt.get_sentiment_data())
    assert out["available"] is True
    assert out["gold"]["fear_greed_index"] == 72
    assert out["gold"]["sentiment"] == "Greed"


def test_source_failure_marks_unavailable():
    dt = DataTools()
    with patch("app.tools.data_tools.urllib.request.urlopen", side_effect=Exception("boom")):
        out = asyncio.run(dt.get_sentiment_data())
    assert out["available"] is False
    assert out["gold"]["sentiment"] is None
