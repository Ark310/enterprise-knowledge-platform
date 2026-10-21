from restscraper.guard import AssetCache, cacheable, classify


def test_api_hosts_are_flagged():
    assert classify("GET", "https://apisandbox.contoso.example/token") == "api"
    assert classify("POST", "https://apisandbox.contoso.example/V1/web/Deal/WebDeal") == "api"
    assert classify("GET", "https://contoso.example/x") == "api"


def test_only_get_to_docs_and_assets():
    assert classify("GET", "https://apidocs.contoso.example/deal/x") == "allow"
    assert classify("GET", "https://apidocs.contoso.example/_next/static/a.js") == "allow"
    assert classify("POST", "https://apidocs.contoso.example/x") == "block"
    assert classify("PUT", "https://apidocs.contoso.example/x") == "block"
    assert classify("GET", "https://theneo-prod-public.s3.us-east-1.amazonaws.com/a.png") == "allow"
    assert classify("GET", "https://theneo-prod-public.s3.amazonaws.com/a.ico") == "allow"
    assert classify("GET", "https://fonts.gstatic.com/s/x.woff2") == "allow"
    assert classify("GET", "https://cdn.jsdelivr.net/npm/monaco-editor@0.43.0/min/vs/loader.js") == "allow"
    assert classify("GET", "https://cdn.jsdelivr.net/npm/other-lib@1/x.js") == "block"


def test_everything_else_blocked():
    assert classify("GET", "https://www.googletagmanager.com/gtag/js") == "block"
    assert classify("GET", "https://evil-theneo-prod-public.s3.amazonaws.com.attacker.io/a") == "block"
    assert classify("GET", "https://apidocs.contoso.example.attacker.io/") != "allow"
    assert classify("GET", "data:image/png;base64,AAAA") == "allow"


def test_runner_proxy_paths_blocked():
    assert classify("GET", "https://apidocs.contoso.example/api/proxy?url=x") == "block"
    assert classify("GET", "https://apidocs.contoso.example/api/run") == "block"


def test_cacheable_assets_only():
    assert cacheable("https://apidocs.contoso.example/_next/static/chunks/main-1.js")
    assert cacheable("https://theneo-prod-public.s3.amazonaws.com/images-1.png")
    assert not cacheable("https://apidocs.contoso.example/deal/create-web-deal")
    assert not cacheable("https://apidocs.contoso.example/deal/x.md")
    assert not cacheable("https://www.googletagmanager.com/gtag/js")


def test_asset_cache_limits():
    c = AssetCache(max_bytes=10)
    c.put("a", 200, {"Content-Type": "text/js", "Set-Cookie": "x"}, b"12345")
    c.put("b", 404, {}, b"1")
    c.put("big", 200, {}, b"x" * 20)
    assert c.get("a") == (200, {"Content-Type": "text/js"}, b"12345")
    assert c.get("b") is None and c.get("big") is None and c.hits == 1
