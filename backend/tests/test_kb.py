import httpx

from app.agent.kb import KnowledgeBase, build_chunks, chunks_from_item, fetch_items, html_to_sections, sync
from tests.wp_fixtures import ELECTRICAL, LAND, PRIVACY, STARTER


def test_html_to_sections_keeps_structure():
    sections = html_to_sections(ELECTRICAL["content"]["rendered"])
    headings = [h for h, _ in sections]
    assert headings == ["", "Quick Answer", "What Steel Changes"]
    quick = dict(sections)["Quick Answer"]
    assert "$3–$6 per sq ft" in quick  # entities decoded
    assert "200-amp service entrance | $1,800–$3,500" in quick  # table row kept together
    steel = dict(sections)["What Steel Changes"]
    assert "### Spray foam timing" in steel
    assert "- Missing nail plates — required within 1.25 inches." in steel
    assert "Get the Free Rough-In Checklist" not in steel  # button text dropped...
    assert "The free Rough-In Checklist covers bonding." in steel  # ...but the CTA's description kept
    assert "After the box." in steel  # parsing resumes after the skipped block
    assert "Steel framing wired." in dict(sections)[""]  # captions kept


def test_chunks_carry_title_heading_url():
    chunks = chunks_from_item(ELECTRICAL)
    assert {c.heading for c in chunks} == {"", "Quick Answer", "What Steel Changes"}
    assert all(c.url == ELECTRICAL["link"] for c in chunks)


def test_search_ranks_relevant_section_first():
    kb = KnowledgeBase(build_chunks([ELECTRICAL, LAND]))
    top = kb.search("when does spray foam go in vs electrical inspection", k=2)
    assert top[0].heading == "What Steel Changes"
    assert kb.search("perc test septic zoning")[0].url == LAND["link"]
    assert kb.search("the and of") == []


def test_sync_paginates_skips_policy_pages_and_persists(tmp_path):
    calls = []

    def handler(req: httpx.Request):
        kind = req.url.path.rsplit("/", 1)[-1]
        page = int(req.url.params["page"])
        calls.append((kind, page))
        if kind == "posts":
            data = [ELECTRICAL] if page == 1 else [LAND]
            return httpx.Response(200, json=data, headers={"X-WP-TotalPages": "2"})
        return httpx.Response(200, json=[PRIVACY, STARTER], headers={"X-WP-TotalPages": "1"})

    client = httpx.Client(transport=httpx.MockTransport(handler))
    items = fetch_items("https://barndobible.com/", client)
    assert calls == [("posts", 1), ("posts", 2), ("pages", 1)]
    assert [i["slug"] for i in items] == [
        "barndominium-electrical-rough-in",
        "buying-land-for-a-barndominium",
        "barndominium-starter-kit",
    ]

    kb, path = KnowledgeBase(), str(tmp_path / "kb.json")
    sync(kb, "https://barndobible.com", path, client)
    assert kb.article_count == 3 and kb.synced_at
    again = KnowledgeBase.load(path)
    assert len(again.chunks) == len(kb.chunks)
    assert again.search("starter kit")[0].url == STARTER["link"]


def test_sync_keeps_old_kb_when_site_returns_nothing(tmp_path):
    kb = KnowledgeBase(build_chunks([LAND]))
    empty = httpx.Client(transport=httpx.MockTransport(lambda r: httpx.Response(200, json=[])))
    try:
        sync(kb, "https://barndobible.com", str(tmp_path / "kb.json"), empty)
    except RuntimeError:
        pass
    assert kb.article_count == 1
