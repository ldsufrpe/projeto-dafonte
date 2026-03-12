import pytest
from app.services.erp.utils import unwrap_datasnap

def test_unwrap_datasnap_nested_3():
    payload = {"result": [[[{ "id": 1, "name": "Test" }, { "id": 2, "name": "Test 2" }]]]}
    unwrapped = unwrap_datasnap(payload)
    assert len(unwrapped) == 2
    assert unwrapped[0]["id"] == 1
    assert unwrapped[1]["name"] == "Test 2"

def test_unwrap_datasnap_nested_2():
    payload = {"result": [[{ "id": 1 }]]}
    unwrapped = unwrap_datasnap(payload)
    assert len(unwrapped) == 1
    assert unwrapped[0]["id"] == 1

def test_unwrap_datasnap_flat():
    payload = {"result": [{ "id": 1 }]}
    unwrapped = unwrap_datasnap(payload)
    assert len(unwrapped) == 1

def test_unwrap_datasnap_empty_result():
    assert unwrap_datasnap({"result": []}) == []

def test_unwrap_datasnap_no_result():
    assert unwrap_datasnap({"other": "data"}) == []

def test_unwrap_datasnap_invalid_payload():
    assert unwrap_datasnap("not a dict") == []
