"""Parser tests against real page bodies saved from help.contoso.example."""
from pathlib import Path

from kbscraper.parser import attachment_ref, parse_body, storage_counts, youtube_watch_url

FIX = Path(__file__).parent / "fixtures"


def load(name):
    return parse_body((FIX / f"{name}.html").read_text(encoding="utf-8"), "1")


def test_expand_titles_and_content_are_kept():
    r = load("expand")
    assert [e["title"] for e in r.expands] == ["Click here for the details"] * 2
    assert "Security Questions" in r.expands[0]["markdown"]
    assert "<summary>Click here for the details</summary>" in r.markdown


def test_images_inside_dropdowns_are_resources():
    r = load("expand")
    images = [x for x in r.resources if x["kind"] == "image"]
    assert images and images[0]["filename"] == "onlinesetup1.png"
    assert images[0]["attachment_page_id"] == "26411376"
    assert "{{res:0}}" in r.markdown


def test_code_block_language_title_and_text():
    r = load("code")
    assert r.code_blocks[0]["title"] == "Example Request"
    assert r.code_blocks[0]["language"] == "xml"
    assert r.code_blocks[0]["code"].lstrip().startswith("<INPUT>")
    assert "```xml" in r.markdown


def test_table_rows_are_structured():
    r = load("code")
    t = r.tables[0]
    assert t["headers"][:2] == ["Tag", "Type"]
    assert t["rows"] and "records" in t


def test_video_and_youtube_embed():
    v = load("video")
    assert [x["kind"] for x in v.resources] == ["video"]
    assert v.resources[0]["filename"].endswith(".mp4")
    w = load("widget")
    embeds = [x for x in w.resources if x["kind"] == "embed"]
    assert youtube_watch_url(embeds[0]["src"]) == "https://www.youtube.com/watch?v=I0iJsmIrtz8"


def test_embedded_file_is_a_file_not_a_placeholder_image():
    r = load("viewfile")
    kinds = {x["filename"]: x["kind"] for x in r.resources}
    assert kinds["ForexRatesUploadSample.csv"] == "file"
    assert "placeholder-medium-file.png" not in kinds


def test_headings_without_bold_markers():
    r = load("viewfile")
    assert r.headings[0]["text"] == "Enhancements and New Features"
    assert r.markdown.startswith("## Enhancements and New Features")


def test_nested_expands_inside_tables():
    r = load("viewfile")
    assert len(r.expands) == 7


def test_storage_counts():
    s = ('<ac:structured-macro ac:name="expand"></ac:structured-macro>'
         '<ac:structured-macro ac:name="code"></ac:structured-macro><ac:image></ac:image>'
         '<ac:structured-macro ac:name="multimedia"/><table></table>'
         '<ac:structured-macro ac:name="widget"/><ac:macro ac:name="expand"></ac:macro>')
    assert storage_counts(s) == {"expands": 2, "code_blocks": 1, "images": 1, "videos": 1,
                                 "embeds": 1, "tables": 1}


def test_attachment_ref_handles_thumbnails_and_encoding():
    assert attachment_ref("https://help.contoso.example/download/thumbnails/12/a%20b.png?version=1") == ("12", "a b.png")
    assert attachment_ref("https://example.com/x.png") is None


def test_skips_search_and_toc_macros():
    html = ('<div data-macro-name="livesearch"><input placeholder="Search"/>Search</div>'
            '<div class="toc-macro">TOC</div><p>Body</p>')
    r = parse_body(html, "1")
    assert r.markdown == "Body"
