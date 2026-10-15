"""Website agent: chat with a simulated Claude, the estimator endpoint, guards, CORS and the widget."""

import json

import httpx
import pytest

from app.agent.kb import KnowledgeBase, build_chunks
from app.agent.llm import AnthropicClient
from app.agent.service import Agent
from app.routers import public
from tests.conftest import h
from tests.wp_fixtures import ELECTRICAL, LAND

URL = ELECTRICAL["link"]


class FakeClaude:
    """Mock transport that plays scripted Anthropic responses and records requests."""

    def __init__(self, responses):
        self.responses, self.requests = list(responses), []

    def __call__(self, req: httpx.Request):
        self.requests.append(req)
        return httpx.Response(200, json=self.responses.pop(0))


def text_reply(text):
    return {
        "type": "message",
        "stop_reason": "end_turn",
        "content": [{"type": "text", "text": text}],
        "usage": {"input_tokens": 100, "output_tokens": 20},
    }


def tool_reply(name, args):
    return {
        "type": "message",
        "stop_reason": "tool_use",
        "usage": {"input_tokens": 50, "output_tokens": 10},
        "content": [
            {"type": "text", "text": "Let me check."},
            {"type": "tool_use", "id": "toolu_1", "name": name, "input": args},
        ],
    }


@pytest.fixture()
def kb():
    return KnowledgeBase(build_chunks([ELECTRICAL, LAND]))


def use_agent(client, kb, fake):
    llm = AnthropicClient("sk-test", "claude-sonnet-5-5", client=httpx.Client(transport=httpx.MockTransport(fake)))
    client.app.dependency_overrides[public.get_agent] = lambda: Agent(llm, kb)


def ask(client, text, history=()):
    return client.post("/public/chat", json={"messages": [*history, {"role": "user", "content": text}]})


# ---------------------------------------------------------------- agent behaviour
def test_answer_is_grounded_and_cites_sources(client, kb):
    fake = FakeClaude([text_reply(f"Rough-in must pass inspection before spray foam. See [the guide]({URL}).")])
    use_agent(client, kb, fake)
    r = ask(client, "When does spray foam go in vs electrical?")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["sources"] == [{"title": ELECTRICAL["title"]["rendered"], "url": URL}]
    assert body["estimate"] is None

    sent = fake.requests[0]
    assert sent.headers["x-api-key"] == "sk-test"
    assert sent.headers["anthropic-version"] == "2023-06-01"
    payload = json.loads(sent.content)
    assert payload["model"] == "claude-sonnet-5-5"
    assert payload["system"][0]["cache_control"] == {"type": "ephemeral"}
    assert "spray foam" in payload["system"][1]["text"].lower()  # retrieved excerpt injected
    assert {t["name"] for t in payload["tools"]} == {"search_guides", "estimate_materials", "find_builders"}


def test_estimator_tool_round_trip(client, kb):
    fake = FakeClaude(
        [
            tool_reply("estimate_materials", {"width_ft": 40, "length_ft": 60}),
            text_reply("You'll need about 46.5 cubic yards of concrete."),
        ]
    )
    use_agent(client, kb, fake)
    r = ask(client, "How much concrete for a 40x60?")
    assert r.status_code == 200
    assert r.json()["estimate"]["summary"]["concrete_cy"] == 46.5
    second = json.loads(fake.requests[1].content)["messages"]
    assert second[-2]["role"] == "assistant" and second[-2]["content"][1]["type"] == "tool_use"
    result = second[-1]["content"][0]
    assert result["type"] == "tool_result" and result["tool_use_id"] == "toolu_1"
    assert json.loads(result["content"])["summary"]["concrete_cy"] == 46.5


def test_bad_tool_input_is_reported_to_model_not_user(client, kb):
    fake = FakeClaude(
        [
            tool_reply("estimate_materials", {"width_ft": 4000, "length_ft": 60}),
            text_reply("That width is out of range; what are the real dimensions?"),
        ]
    )
    use_agent(client, kb, fake)
    r = ask(client, "Estimate a 4000 ft wide barn")
    assert r.status_code == 200
    result = json.loads(fake.requests[1].content)["messages"][-1]["content"][0]
    assert result["is_error"] is True and "width_ft" in result["content"]


def test_search_tool_adds_sources(client, kb):
    fake = FakeClaude(
        [
            tool_reply("search_guides", {"query": "zoning deed restrictions"}),
            text_reply(f"Check zoning first: {LAND['link']}"),
        ]
    )
    use_agent(client, kb, fake)
    r = ask(client, "Anything to know before an offer?")
    assert {s["url"] for s in r.json()["sources"]} == {LAND["link"]}


def test_history_is_trimmed_and_starts_with_user(client, kb, monkeypatch):
    monkeypatch.setenv("CHAT_MAX_HISTORY", "2")
    from app.config import get_settings

    get_settings.cache_clear()
    fake = FakeClaude([text_reply("ok")])
    use_agent(client, kb, fake)
    hist = [
        {"role": "user", "content": f"q{i}"} if i % 2 == 0 else {"role": "assistant", "content": f"a{i}"}
        for i in range(6)
    ]
    ask(client, "latest", hist)
    msgs = json.loads(fake.requests[0].content)["messages"]
    assert msgs[0]["role"] == "user" and msgs[-1]["content"] == "latest" and len(msgs) <= 3


def test_upstream_error_gives_friendly_502(client, kb):
    def boom(req):
        return httpx.Response(529, json={"error": {"message": "Overloaded"}})

    use_agent(client, kb, boom)
    r = ask(client, "hello")
    assert r.status_code == 502 and "trouble" in r.json()["detail"]
    assert "sk-test" not in r.text


# ---------------------------------------------------------------- guards
def test_not_configured_without_key(client):
    r = ask(client, "hi")
    assert r.status_code == 503


def test_validation(client, kb):
    use_agent(client, kb, FakeClaude([]))
    assert client.post("/public/chat", json={"messages": [{"role": "assistant", "content": "x"}]}).status_code == 422
    assert ask(client, "x" * 2001).status_code == 413


def test_rate_limit_per_ip(client, kb, monkeypatch):
    monkeypatch.setenv("PUBLIC_RATE_LIMIT", "2")
    from app.config import get_settings

    get_settings.cache_clear()
    public._limiter.cache_clear()
    use_agent(client, kb, FakeClaude([text_reply("a"), text_reply("b")]))
    assert ask(client, "one").status_code == 200
    assert ask(client, "two").status_code == 200
    r = ask(client, "three")
    assert r.status_code == 429 and int(r.headers["Retry-After"]) > 0


def test_daily_cap(client, kb, monkeypatch):
    monkeypatch.setenv("AGENT_DAILY_LIMIT", "1")
    from app.config import get_settings

    get_settings.cache_clear()
    public._limiter.cache_clear()
    use_agent(client, kb, FakeClaude([text_reply("a")]))
    assert ask(client, "one").status_code == 200
    r = ask(client, "two")
    assert r.status_code == 429 and "today" in r.json()["detail"]
    assert client.get("/admin/agent/usage", headers=h("admin")).json() == {"chats_today": 1, "daily_limit": 1}


# ---------------------------------------------------------------- estimate endpoint, status, CORS, widget
def test_public_estimate(client):
    r = client.post("/public/estimate", json={"width_ft": 40, "length_ft": 60})
    assert r.status_code == 200 and r.json()["summary"]["concrete_cy"] == 46.5
    assert client.post("/public/estimate", json={"width_ft": 5, "length_ft": 60}).status_code == 422


def test_budget_limits_reach_public_and_chat_estimates(client, kb):
    """Both consumers receive the limits, not just the widget's visible copy."""
    args = {"width_ft": 40, "length_ft": 60}
    result = client.post("/public/estimate", json=args).json()
    assert "not an engineered design or an order list" in result["assumptions"][0]
    assert "not recommendations for your site" in result["assumptions"][1]
    fake = FakeClaude([tool_reply("estimate_materials", args), text_reply("Preliminary quantities only.")])
    use_agent(client, kb, fake)
    response = ask(client, "Estimate materials for a 40x60 building").json()
    sent = json.loads(fake.requests[1].content)["messages"][-1]["content"][0]
    tool_result = json.loads(sent["content"])
    assert tool_result["assumptions"] == result["assumptions"]
    assert response["estimate"]["summary"] == result["summary"]


def test_cost_and_source_rules_sent_on_followup(client, kb):
    """Check actual request construction; this does not evaluate model compliance."""
    fake = FakeClaude([text_reply("What state, living/shop split and build scope?")])
    use_agent(client, kb, fake)
    ask(client, "What does a 40x60 cost?", [{"role": "user", "content": "I am planning a barndo"}])
    payload = json.loads(fake.requests[0].content)
    policy = payload["system"][0]["text"]
    assert "before presenting dollar ranges" in policy
    assert "Never infer foundation design from state or soil color" in policy
    assert "never say the sequence is identical everywhere" in policy
    assert payload["messages"][-1]["content"] == "What does a 40x60 cost?"


def test_status(client):
    s = client.get("/public/status").json()
    assert s["assistant_configured"] is False and s["knowledge_base"]["articles"] == 0


def test_cors_allows_only_the_site(client):
    pre = {"Access-Control-Request-Method": "POST", "Access-Control-Request-Headers": "content-type"}
    ok = client.options("/public/chat", headers={"Origin": "https://barndobible.com", **pre})
    assert ok.headers.get("access-control-allow-origin") == "https://barndobible.com"
    bad = client.options("/public/chat", headers={"Origin": "https://evil.example", **pre})
    assert "access-control-allow-origin" not in bad.headers


def test_widget_is_served(client):
    js = client.get("/widget/barndo-agent.js")
    assert js.status_code == 200 and "javascript" in js.headers["content-type"]
    assert "attachShadow" in js.text
    assert client.get("/widget/").status_code == 200


def test_kb_refresh_requires_admin(client):
    assert client.post("/admin/kb/refresh", headers=h("manager")).status_code == 403


def test_builder_tool_returns_public_matches(client, kb, monkeypatch):
    monkeypatch.setattr(
        "app.routers.directory.public_companies",
        lambda: [
            {
                "name": "Example",
                "source": "https://example.com",
                "areas": ["Paris"],
                "work_types": ["complete"],
                "availability": "unknown",
            }
        ],
    )
    fake = FakeClaude(
        [
            tool_reply("find_builders", {"area": "Paris", "work_type": "complete"}),
            text_reply("Contact [Example](https://example.com); confirm availability."),
        ]
    )
    use_agent(client, kb, fake)
    response = ask(client, "Builders in Paris for a complete home?")
    assert response.status_code == 200
    result = json.loads(fake.requests[1].content)["messages"][-1]["content"][0]
    assert json.loads(result["content"])["companies"][0]["availability"] == "unknown"
