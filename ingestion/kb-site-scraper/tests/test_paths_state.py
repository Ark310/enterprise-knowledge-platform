import json

from kbscraper.discovery import ArticleInfo, SpaceInfo, assign_folders
from kbscraper.paths import safe_filename, safe_segment
from kbscraper.state import DONE, FAILED, PENDING, RunState


def test_safe_segment_windows_rules():
    assert safe_segment('Error: BI System / "Login"?') == "Error- BI System - -Login--"
    assert safe_segment("CON") == "CON_"
    assert safe_segment("ends with dot. ") == "ends with dot"
    assert len(safe_segment("word " * 40)) <= 80
    assert safe_segment("   ") == "untitled"


def test_safe_filename_keeps_extension():
    name = safe_filename("x" * 300 + ".png")
    assert name.endswith(".png") and len(name) <= 100
    assert safe_filename("a:b?.jpg") == "a_b_.jpg"


def _art(pid, title, parent=""):
    return ArticleInfo(page_id=pid, title=title, content_type="page", space_key="S",
                       url="u", version=1, parent_id=parent)


def test_folders_mirror_tree_and_are_unique():
    sp = SpaceInfo(key="S", name="S", product="p", product_label="P", folder="p/s")
    arts = [_art("1", "Home"), _art("2", "Child", "1"), _art("3", "child", "1"),
            _art("4", "Grand", "2"), _art("5", "images", "1"), _art("6", "Orphan", "999")]
    assign_folders(sp, arts)
    f = {a.page_id: a.folder for a in arts}
    assert f["1"] == "p/s/Home"
    assert f["4"] == "p/s/Home/Child/Grand"
    assert f["2"].lower() != f["3"].lower()            # case-insensitive collision resolved
    assert f["5"] == "p/s/Home/images [5]"              # cannot shadow the images/ folder
    assert f["6"] == "p/s/Orphan"                       # missing parent -> space root


def test_state_journal_survives_crash(tmp_path):
    st = RunState.create([{"page_id": "1", "title": "a"}, {"page_id": "2", "title": "b"}],
                         {"kind": "test"}, runs_dir=tmp_path)
    st.update("1", status=DONE)
    st.update("2", status=FAILED, error="boom")
    # simulate a hard kill: no compact; append a torn line
    with open(st.folder / "journal.jsonl", "a", encoding="utf-8") as fh:
        fh.write('{"page_id": "2", "sta')
    loaded = RunState.load(st.run_id, runs_dir=tmp_path)
    assert loaded.articles["1"]["status"] == DONE
    assert loaded.articles["2"]["status"] == FAILED and loaded.articles["2"]["error"] == "boom"
    assert RunState.latest_id(runs_dir=tmp_path) == st.run_id
    assert loaded.ids_with_status(PENDING) == []
    assert json.loads((st.folder / "manifest.json").read_text(encoding="utf-8"))["meta"]["kind"] == "test"
