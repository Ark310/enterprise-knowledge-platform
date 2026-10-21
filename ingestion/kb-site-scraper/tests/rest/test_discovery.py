from pathlib import Path

from restscraper import theneo
from restscraper.discovery import SiteMap, build_sitemap, crosscheck

FIXTURE = Path(__file__).parent / "fixtures" / "page.html"


def _pp():
    return theneo.next_data(FIXTURE.read_text(encoding="utf-8"))


def _item(name, slug, sid, sub=()):
    return {"name": name, "slug": slug, "sectionId": sid, "subItems": list(sub),
            "isHeader": False, "externalPageLink": ""}


def _synthetic_pp(items, slugs=None):
    return {"documents": {"data": {"documentMenu": {"items": items, "slugs": slugs or {}},
                                   "transformedSection": []}}}


def test_section_folders_numbered_in_menu_order():
    sm = build_sitemap(_pp(), [])
    assert [s.folder for s in sm.sections] == ["01 Getting Started", "02 Authorization"]
    login = next(p for p in sm.pages if p.slug == "authorization/login-via-web-user")
    assert login.folder == "02 Authorization/Login (via web user)"
    assert login.kind == "endpoint" and login.section_key == "authorization"
    assert login.url == "https://apidocs.contoso.example/authorization/login-via-web-user"
    gs = next(p for p in sm.pages if p.slug == "getting-started-1")
    assert gs.kind == "section" and gs.folder == "01 Getting Started"


def test_folders_unique_for_duplicate_names():
    pp = _synthetic_pp([_item("Admin", "admin", "s1", [
        _item("Reset Password (via web user)", "reset-password-via-web-user", "a"),
        _item("Reset Password (via web user)", "reset-password-via-web-user-1", "b"),
        _item("Images", "images", "c"),
    ])])
    folders = [p.folder for p in build_sitemap(pp, []).pages]
    assert folders[0] == "01 Admin"
    assert folders[1] == "01 Admin/Reset Password (via web user)"
    assert folders[2] == "01 Admin/Reset Password (via web user) [reset-password-via-web-user-1]"
    assert folders[3] == "01 Admin/Images [images]"          # cannot shadow the images/ folder


def test_crosscheck_uses_slug_aliases():
    pp = _synthetic_pp(
        [_item("Bank", "bank", "s1", [_item("Update", "update-x-1", "a"), _item("Gone", "gone", "g")])],
        slugs={"update-x": "a", "update-x-1": "a", "bank": "s1", "gone": "g"})
    rep = crosscheck(pp, ["bank", "bank/update-x", "bank/unknown"])
    assert rep["missing_from_menu"] == ["bank/unknown"]
    assert rep["missing_from_llms"] == ["bank/gone"]
    assert rep["menu"] == 3 and rep["llms"] == 3


def test_crosscheck_pairs_renamed_slugs():
    pp = _synthetic_pp([_item("Cheque", "cheque", "s1", [_item("Get", "get-cheques-via-web-user-1", "a")])])
    rep = crosscheck(pp, ["cheque", "cheque/get-cheques-via-web-user"])
    assert rep["renamed"] == {"cheque/get-cheques-via-web-user": "cheque/get-cheques-via-web-user-1"}
    assert rep["missing_from_menu"] == [] and rep["missing_from_llms"] == []


def test_records_and_roundtrip(tmp_path):
    sm = build_sitemap(_pp(), [])
    recs = sm.records(section_keys={"authorization"})
    assert {r["slug"] for r in recs} == {"authorization", "authorization/login-via-web-user",
                                         "authorization/login-via-td-user"}
    r = recs[0]
    assert {"page_id", "title", "space_key", "space_name", "folder", "url", "kind"} <= set(r)
    path = tmp_path / "sitemap.json"
    sm.save(path)
    again = SiteMap.load(path)
    assert again.records() == sm.records()
    assert SiteMap.load(tmp_path / "nope.json") is None
