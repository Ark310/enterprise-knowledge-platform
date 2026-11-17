import json
from pathlib import Path

import pytest

from restscraper import theneo

FIXTURE = Path(__file__).parent / "fixtures" / "page.html"


@pytest.fixture(scope="module")
def pp():
    if not FIXTURE.exists():
        pytest.skip("captured API docs page not shipped")
    return theneo.next_data(FIXTURE.read_text(encoding="utf-8"))


def _entry(pp, slug):
    return next(s for s in pp["documents"]["data"]["transformedSection"] if s.get("slug") == slug)


def test_next_data_extracts_page_props(pp):
    assert "documentMenu" in pp["documents"]["data"]


def test_next_data_missing_raises():
    with pytest.raises(ValueError):
        theneo.next_data("<html><title>403 Forbidden</title></html>")


def test_menu_items_and_aliases(pp):
    items = theneo.menu_items(pp)
    assert [i["slug"] for i in items] == ["getting-started-1", "authorization"]
    aliases = theneo.slug_aliases(pp)
    assert aliases["access-create-token"] == "65b7840596cfe291c48331c2"


def test_section_entry_by_id(pp):
    e = theneo.section_entry(pp, "65b7840596cfe291c48331c2")
    assert e["name"] == "Login (via web user)"
    assert theneo.section_entry(pp, "nope") is None


def test_normalize_params_nested():
    raw = [{"name": "detail", "valueType": "object", "isRequired": True, "description": "d",
            "value": "", "items": [{"name": "client", "valueType": "object", "value": "",
                                    "items": [{"name": "id", "valueType": "string", "value": "4675",
                                               "items": [], "complexItems": []}],
                                    "complexItems": []}], "complexItems": []}]
    p = theneo.normalize_params(raw)
    assert p[0]["name"] == "detail" and p[0]["required"] is True and p[0]["type"] == "object"
    assert p[0]["children"][0]["children"][0] == {
        "name": "id", "type": "string", "required": False, "description": "",
        "example": "4675", "children": []}


def test_endpoint_info_login(pp):
    info = theneo.endpoint_info(_entry(pp, "authorization/login-via-web-user"))
    assert info["method"] == "POST" and info["path"] == "token"
    assert [p["name"] for p in info["body"]] == ["grant_type", "CustID", "username", "password"]
    assert [r["status"] for r in info["responses"]] == [200, 400]
    ok = json.loads(info["responses"][0]["example"])
    assert ok["status"] is True and ok["data"]["token_type"] == "bearer"


def test_example_from_array_params():
    params = theneo.normalize_params([
        {"name": "ids", "valueType": "array", "value": "", "complexItems": [],
         "items": [{"name": "", "valueType": "number", "value": 7, "items": [], "complexItems": []}]},
        {"name": "rows", "valueType": "array", "value": "", "complexItems": [],
         "items": [{"name": "a", "valueType": "string", "value": "x", "items": [], "complexItems": []}]},
    ])
    assert theneo.example_from_params(params) == {"ids": [7], "rows": [{"a": "x"}]}


def test_expected_counts(pp):
    c = theneo.expected_counts(_entry(pp, "authorization/login-via-web-user"))
    assert c["responses"] == 2 and c["body"] == 4 and c["header"] >= 2


def test_verify_counts_no_responses(pp):
    c = theneo.expected_counts(_entry(pp, "authorization"))
    assert c["responses"] == 0 and c["body"] == 0


def test_parse_llms():
    text = ("# Contoso REST API\n"
            "• [Getting Started](https://apidocs.contoso.example/getting-started-1.md): x\n"
            "  • [Login](https://apidocs.contoso.example/authorization/login-via-web-user.md): y\n")
    assert theneo.parse_llms(text) == ["getting-started-1", "authorization/login-via-web-user"]


def test_is_endpoint_without_path(pp):
    assert theneo.is_endpoint({"request": {"body": []}, "endpoints": {"method": "GET", "path": ""}})
    assert not theneo.is_endpoint(_entry(pp, "authorization"))          # section overview
    assert not theneo.is_endpoint(_entry(pp, "getting-started-1"))
    assert theneo.is_endpoint(_entry(pp, "authorization/login-via-web-user"))
