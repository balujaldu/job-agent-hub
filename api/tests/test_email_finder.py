import httpx

from app.agents.email_finder import crawl_for_email, find_emails_in_html, score_email

SITE = {
    "/": '<a href="/careers">Careers</a> <a href="https://twitter.com/acme">Twitter</a> '
         '<a href="mailto:press@acme.com">Press</a>',
    "/careers": "<p>Send your CV to jobs [at] acme [dot] com or apply online.</p>",
    "/contact": '<a href="mailto:info@acme.com">info@acme.com</a> noreply@acme.com',
}


def _client(pages, robots=""):
    def handler(request: httpx.Request):
        path = request.url.path
        if path == "/robots.txt":
            return httpx.Response(200, text=robots) if robots else httpx.Response(404)
        if path in pages:
            return httpx.Response(200, text=pages[path], headers={"content-type": "text/html"})
        return httpx.Response(404)

    return httpx.Client(transport=httpx.MockTransport(handler), follow_redirects=True)


def test_finds_hiring_address_over_general_ones():
    result = crawl_for_email("acme.com", http=_client(SITE))
    assert result.email == "jobs@acme.com"
    assert result.source.endswith("/careers")
    assert "info@acme.com" in [c.email for c in result.alternatives]
    assert "press@acme.com" not in [c.email for c in result.alternatives]


def test_general_inbox_alone_is_not_used():
    pages = {"/": "", "/contact": SITE["/contact"]}
    result = crawl_for_email("https://www.acme.com", http=_client(pages))
    assert result.email == ""
    assert [c.email for c in result.alternatives] == ["info@acme.com"]


def test_respects_robots_txt():
    result = crawl_for_email("acme.com", http=_client(SITE, robots="User-agent: *\nDisallow: /careers"))
    assert result.email == ""


def test_html_extraction_skips_assets_and_decodes_obfuscation():
    html = '<img src="logo@2x.png"> hr (at) acme (dot) io <a href="mailto:Talent@Acme.io?subject=x">x</a>'
    assert find_emails_in_html(html) == ["talent@acme.io", "hr@acme.io"]


def test_scoring():
    assert score_email("careers@acme.com", "acme.com", "") > score_email("info@acme.com", "acme.com", "")
    assert score_email("noreply@acme.com", "acme.com", "") == -100
    assert score_email("jobs@gmail.com", "acme.com", "") < score_email("jobs@acme.com", "acme.com", "")
