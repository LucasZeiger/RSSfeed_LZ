from datetime import UTC, datetime
from unittest.mock import Mock

import pytest

from backend.digest import Brief, BriefItem, render, select_articles, send_telegram
from backend.models import Article, Dataset, RunStatus, Source

NOW = datetime(2026, 11, 25, 19, 7, tzinfo=UTC)
STAMP = NOW.isoformat()


def test_round_robin_selection_uses_recent_uk_articles():
    sources = [
        Source(
            id=source,
            name=source,
            url="https://example.org/rss",
            category="World",
            country=country,
            publisher_id=publisher,
        )
        for source, country, publisher in [
            ("uk-one", "UK", "one"),
            ("uk-one-other", "UK", "one"),
            ("uk-two", "UK", "two"),
            ("us", "US", "us"),
        ]
    ]
    articles = [
        Article(
            id=source.id,
            source_id=source.id,
            title=source.name,
            url=f"https://example.org/{source.id}",
            published_at=STAMP,
            fetched_at=STAMP,
            category="World",
            country=source.country,
        )
        for source in sources
    ]
    dataset = Dataset(
        mode="live",
        generated_at=STAMP,
        articles=articles,
        sources=sources,
        stories=[],
        instruments=[],
        status=RunStatus(state="ok", attempted_at=STAMP),
    )
    selected = select_articles(dataset, NOW)
    assert [source.id for _, source in selected] == ["uk-one", "uk-two", "uk-one-other"]
    brief = Brief(
        stories=[
            BriefItem(
                headline="UK headline", summary="Details https://untrusted.example/", references=[2]
            )
        ]
    )
    message = render(brief, selected, NOW)
    assert "https://example.org/uk-two" in message
    assert "untrusted.example" not in message
    brief.stories[0].references = [99]
    with pytest.raises(ValueError, match="unknown source"):
        render(brief, selected, NOW)


def test_telegram_delivery_disables_previews_and_rejects_unsuccessful_response(monkeypatch):
    client = Mock()
    client.__enter__ = Mock(return_value=client)
    client.__exit__ = Mock(return_value=None)
    client.post.return_value.is_success = True
    client.post.return_value.json.return_value = {"ok": False}
    monkeypatch.setattr("backend.digest.httpx.Client", Mock(return_value=client))
    with pytest.raises(ValueError, match="rejected"):
        send_telegram("brief", "123:dummy", "-123")
    client.post.assert_called_once_with(
        "https://api.telegram.org/bot123:dummy/sendMessage",
        json={"chat_id": "-123", "text": "brief", "link_preview_options": {"is_disabled": True}},
    )
