import json
from types import SimpleNamespace

import httpx
from pydantic import SecretStr

from app.domain.crm.company_research import draft_company_summary
from app.domain.exceptions.list_search import interpret_filters


def test_exception_interpretation_uses_only_the_question(monkeypatch):
    settings = SimpleNamespace(
        openai_api_key=SecretStr("test"), openai_search_model="test-search"
    )

    def post(url, *, headers, json: dict, timeout):
        assert url.endswith("/v1/responses")
        assert json["input"] == "Open A7 alerts from Germany"
        assert json["store"] is False and "tools" not in json
        assert json["text"]["format"]["strict"] is True
        return response(
            {
                "text": '{"supported":true,"error":"A7","market":"DE","work_status":"open","days":30,"q":""}'
            }
        )

    monkeypatch.setattr("app.integration.openai.responses.httpx.post", post)
    draft = interpret_filters("Open A7 alerts from Germany", settings)
    assert draft.error == "A7" and draft.market == "DE" and draft.work_status == "open"


def test_company_research_passes_public_identity_and_returns_sources(monkeypatch):
    settings = SimpleNamespace(
        openai_api_key=SecretStr("test"), openai_web_model="test-web"
    )

    def post(url, *, headers, json: dict, timeout):
        assert (
            json["input"]
            == '{"company_name": "Example AG", "company_domain": "example.test"}'
        )
        assert json["store"] is False and json["tools"] == [{"type": "web_search"}]
        return response(
            {
                "text": "**Example AG** operates in Switzerland. "
                "([example.test](https://example.test/about)) "
                "It publishes [product information](https://example.test/products).",
                "annotations": [
                    {
                        "type": "url_citation",
                        "url": "https://example.test/about",
                        "title": "Company profile",
                    },
                    {
                        "type": "url_citation",
                        "url": "javascript:alert(1)",
                        "title": "Invalid",
                    },
                ],
            }
        )

    monkeypatch.setattr("app.integration.openai.responses.httpx.post", post)
    text, sources = draft_company_summary("Example AG", "example.test", settings)
    assert text == "Example AG operates in Switzerland. It publishes product information."
    assert sources == [("https://example.test/about", "Company profile")]


def response(item):
    return httpx.Response(
        200,
        request=httpx.Request("POST", "https://api.openai.com/v1/responses"),
        content=json.dumps(
            {
                "status": "completed",
                "output": [
                    {"type": "message", "content": [{"type": "output_text", **item}]}
                ],
            }
        ),
    )
