from restscraper.page import verify
from restscraper.render import flatten_params, html_to_md, page_markdown
from restscraper.settings import LANGUAGES

ALL = {label: "code" for label, _k, _e in LANGUAGES}


def _found(**kw):
    base = {"endpoint": True, "rendered": True, "snippets": dict(ALL), "responses": 2,
            "tryit": True, "tryit_header_fields": 4, "tryit_body": True, "tryit_snippets": 8,
            "images_found": 1, "images_saved": 1, "screenshots": 1, "api_hits": []}
    base.update(kw)
    return base


EXPECTED = {"header": 4, "query": 0, "path": 0, "body": 4, "responses": 2, "images": 1}


def test_verify_clean_endpoint():
    issues, _notes = verify(EXPECTED, _found(), screenshots=True)
    assert issues == []


def test_verify_flags_missing_snippet_and_tabs():
    snippets = dict(ALL)
    del snippets["Go"]
    issues, _ = verify(EXPECTED, _found(snippets=snippets, responses=1), screenshots=True)
    assert any("Go" in i for i in issues)
    assert any("1 of 2 response" in i for i in issues)


def test_verify_counts_no_responses():
    exp = dict(EXPECTED, responses=0, body=0, images=0)
    issues, _ = verify(exp, _found(responses=0, tryit_body=False, images_found=0, images_saved=0),
                       screenshots=True)
    assert issues == []


def test_verify_safety_and_tryit():
    issues, _ = verify(EXPECTED, _found(api_hits=["POST https://apisandbox.contoso.example/token"],
                                        tryit_header_fields=2, tryit_body=False), screenshots=True)
    assert any(i.startswith("SAFETY") for i in issues)
    assert any("2 of 4 header" in i for i in issues)
    assert any("body" in i.lower() for i in issues)


def test_verify_section_page():
    exp = {"header": 0, "query": 0, "path": 0, "body": 0, "responses": 0, "images": 0}
    issues, _ = verify(exp, {"endpoint": False, "rendered": True, "images_found": 0, "images_saved": 0,
                             "screenshots": 0, "api_hits": []}, screenshots=True)
    assert issues == ["No screenshot was saved"]


def test_flatten_params_dotted():
    params = [{"name": "detail", "type": "object", "required": True, "description": "", "example": "",
               "children": [{"name": "client", "type": "object", "required": False, "description": "",
                             "example": "", "children": [
                                 {"name": "id", "type": "string", "required": False, "description": "x",
                                  "example": "4675", "children": []}]}]}]
    rows = flatten_params(params)
    assert [r["name"] for r in rows] == ["detail", "detail.client", "detail.client.id"]


def test_html_to_md_table_and_links():
    html = ('<p class="slate-p">Intro <strong>bold</strong></p><div class="table-container"><table>'
            '<div class="published-table-header" style="visibility: hidden"><div>Stale</div></div>'
            '<tbody><tr><div><td><p><a href="https://x/a">A</a></p></td></div><div><td>B|C</td></div></tr>'
            '<tr><div><td>1</td></div><div><td>2</td></div></tr></tbody></table></div>')
    md = html_to_md(html)
    assert "Intro **bold**" in md
    assert "| [A](https://x/a) | B\\|C |" in md
    assert "| 1 | 2 |" in md
    assert "Stale" not in md


def test_page_markdown_has_param_rows_and_snippets():
    doc = {"title": "Create Web Deal", "url": "https://u", "breadcrumb": ["Deal", "Create Web Deal"],
           "endpoint": {"method": "POST", "path": "V1/web/Deal/WebDeal", "request_url": "https://apisandbox.contoso.example/V1/web/Deal/WebDeal",
                        "headers": [], "path_params": [], "query": [],
                        "body": [{"name": "detail", "type": "object", "required": True, "description": "",
                                  "example": "", "children": [{"name": "client", "type": "object",
                                  "required": False, "description": "", "example": "", "children": [
                                      {"name": "id", "type": "string", "required": False,
                                       "description": "", "example": "4675", "children": []}]}]}],
                        "responses": [{"status": 200, "description": "OK", "example": "{}"}]},
           "content": {"markdown": "Some text"},
           "snippets": [{"language": "cURL", "file": "snippets/curl.sh", "code": "curl x"}],
           "responses_rendered": {"200": "{\n}"},
           "tryit": {"url": "https://runner", "fields": [{"group": "Header Parameters", "name": "Accept",
                                                          "value": "application/json"}]}}
    md = page_markdown(doc)
    assert md.startswith("# Create Web Deal")
    assert "`POST` `https://apisandbox.contoso.example/V1/web/Deal/WebDeal`" in md
    assert "| detail.client.id | string |" in md
    assert "```bash\ncurl x\n```" in md
    assert "| Header Parameters | Accept | application/json |" in md


def test_verify_tryit_unavailable_on_site_is_a_note():
    issues, notes = verify(EXPECTED, _found(tryit=True, tryit_unavailable=True, tryit_header_fields=0,
                                            tryit_body=False, tryit_snippets=0), screenshots=True)
    assert issues == [] and any("does not offer" in n for n in notes)
