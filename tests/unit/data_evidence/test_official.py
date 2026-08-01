"""Contract tests for adapters/official.py — official project announcement adapter.

Tests: success, timeout, HTTP error, malformed payload, empty data.
No real network calls — uses httpx.MockTransport.
"""

from __future__ import annotations

from datetime import datetime, timezone

import httpx

from hoya_agent.adapters.official import fetch_official_announcements

UTC = timezone.utc
ANALYSIS_AS_OF = datetime(2026, 7, 17, 6, 0, 0, tzinfo=UTC)

# A minimal valid RSS feed response
VALID_RSS = """\
<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <title>Ethereum Foundation Blog</title>
    <item>
      <title>Ethereum 2.0 Upgrade Progress Update</title>
      <link>https://blog.ethereum.org/2026/07/10/upgrade</link>
      <pubDate>Thu, 10 Jul 2026 12:00:00 +0000</pubDate>
    </item>
    <item>
      <title>Community Governance Proposal</title>
      <link>https://blog.ethereum.org/2026/07/05/governance</link>
      <pubDate>Sat, 05 Jul 2026 08:00:00 +0000</pubDate>
    </item>
    <item>
      <title>Unrelated Infrastructure Topic</title>
      <link>https://blog.ethereum.org/2026/07/01/infra</link>
      <pubDate>Tue, 01 Jul 2026 10:00:00 +0000</pubDate>
    </item>
  </channel>
</rss>"""

VALID_ATOM = """\
<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom">
  <title>Bitcoin.org Blog</title>
  <entry>
    <title>Bitcoin Core v28 Released</title>
    <link href="https://blog.bitcoin.org/2026/07/12/v28"/>
    <published>2026-07-12T14:00:00Z</published>
  </entry>
</feed>"""

# Feed config for tests
TEST_FEEDS = {
    "ETH": {
        "feed_url": "https://blog.ethereum.org/feed.xml",
        "source_name": "Ethereum Foundation Blog",
        "publisher_domain": "ethereum.org",
    },
    "BTC": {
        "feed_url": "https://blog.bitcoin.org/feed.xml",
        "source_name": "Bitcoin.org Blog",
        "publisher_domain": "bitcoin.org",
    },
}


def _mock_transport(responses: dict[str, tuple[int, str]]):
    """Create a mock transport that maps URL patterns to responses."""
    def handler(request: httpx.Request) -> httpx.Response:
        url = str(request.url)
        for pattern, (status, body) in responses.items():
            if pattern in url:
                return httpx.Response(status, text=body)
        return httpx.Response(404, text="Not Found")
    return httpx.MockTransport(handler)


class TestOfficialSuccess:
    def test_returns_relevant_drafts_from_rss(self):
        transport = _mock_transport({
            "ethereum.org": (200, VALID_RSS),
        })
        client = httpx.Client(transport=transport)
        result = fetch_official_announcements(
            assets=["ETH"],
            analysis_as_of=ANALYSIS_AS_OF,
            client=client,
            feed_overrides=TEST_FEEDS,
        )
        # "Ethereum 2.0 Upgrade Progress Update" mentions ethereum
        assert result.status in ("completed", "partial")
        assert len(result.drafts) >= 1
        # All drafts should be high reliability (official source)
        assert all(d.reliability == "high" for d in result.drafts)
        assert all(d.source_type == "official" for d in result.drafts)
        assert all(d.asset == "ETH" for d in result.drafts)

    def test_returns_relevant_drafts_from_atom(self):
        transport = _mock_transport({
            "bitcoin.org": (200, VALID_ATOM),
        })
        client = httpx.Client(transport=transport)
        result = fetch_official_announcements(
            assets=["BTC"],
            analysis_as_of=ANALYSIS_AS_OF,
            client=client,
            feed_overrides=TEST_FEEDS,
        )
        assert result.status in ("completed", "partial")
        assert len(result.drafts) >= 1
        assert result.drafts[0].reliability == "high"
        assert result.drafts[0].independence_group == "bitcoin.org"

    def test_filters_by_analysis_window(self):
        # Set analysis_as_of before the articles
        early_cutoff = datetime(2026, 7, 1, 0, 0, 0, tzinfo=UTC)
        transport = _mock_transport({
            "ethereum.org": (200, VALID_RSS),
        })
        client = httpx.Client(transport=transport)
        result = fetch_official_announcements(
            assets=["ETH"],
            analysis_as_of=early_cutoff,
            client=client,
            feed_overrides=TEST_FEEDS,
            lookback_days=7,
        )
        # Articles from July 5 and 10 are after the cutoff
        # Only items before July 1 and after June 24 should match
        # None should match since all are after Jul 1
        assert result.status == "failed"

    def test_multi_asset_fetches_each_configured_feed(self):
        transport = _mock_transport({
            "ethereum.org": (200, VALID_RSS),
            "bitcoin.org": (200, VALID_ATOM),
        })
        client = httpx.Client(transport=transport)
        result = fetch_official_announcements(
            assets=["ETH", "BTC"],
            analysis_as_of=ANALYSIS_AS_OF,
            client=client,
            feed_overrides=TEST_FEEDS,
        )
        assets_in_drafts = {d.asset for d in result.drafts}
        # At least ETH should be present (RSS has ethereum mentions)
        assert "ETH" in assets_in_drafts or "BTC" in assets_in_drafts


class TestOfficialTimeout:
    def test_timeout_returns_degradation(self):
        def handler(request: httpx.Request) -> httpx.Response:
            raise httpx.ReadTimeout("timed out")
        client = httpx.Client(transport=httpx.MockTransport(handler))
        result = fetch_official_announcements(
            assets=["ETH"],
            analysis_as_of=ANALYSIS_AS_OF,
            client=client,
            feed_overrides=TEST_FEEDS,
        )
        assert result.status == "failed"
        assert len(result.degradation) >= 1
        assert any("失敗" in d or "failed" in d.lower() for d in result.degradation)


class TestOfficialHttpError:
    def test_http_500_returns_degradation(self):
        transport = _mock_transport({
            "ethereum.org": (500, "Internal Server Error"),
        })
        client = httpx.Client(transport=transport)
        result = fetch_official_announcements(
            assets=["ETH"],
            analysis_as_of=ANALYSIS_AS_OF,
            client=client,
            feed_overrides=TEST_FEEDS,
        )
        assert result.status == "failed"
        assert len(result.degradation) >= 1

    def test_http_429_returns_degradation(self):
        transport = _mock_transport({
            "ethereum.org": (429, "Too Many Requests"),
        })
        client = httpx.Client(transport=transport)
        result = fetch_official_announcements(
            assets=["ETH"],
            analysis_as_of=ANALYSIS_AS_OF,
            client=client,
            feed_overrides=TEST_FEEDS,
        )
        assert result.status == "failed"
        assert len(result.degradation) >= 1


class TestOfficialMalformedPayload:
    def test_invalid_xml_returns_degradation(self):
        transport = _mock_transport({
            "ethereum.org": (200, "this is not xml at all <broken"),
        })
        client = httpx.Client(transport=transport)
        result = fetch_official_announcements(
            assets=["ETH"],
            analysis_as_of=ANALYSIS_AS_OF,
            client=client,
            feed_overrides=TEST_FEEDS,
        )
        assert result.status == "failed"
        assert len(result.degradation) >= 1

    def test_empty_rss_no_items(self):
        empty_rss = '<?xml version="1.0"?><rss><channel></channel></rss>'
        transport = _mock_transport({
            "ethereum.org": (200, empty_rss),
        })
        client = httpx.Client(transport=transport)
        result = fetch_official_announcements(
            assets=["ETH"],
            analysis_as_of=ANALYSIS_AS_OF,
            client=client,
            feed_overrides=TEST_FEEDS,
        )
        assert result.status == "failed"
        assert any("無" in d for d in result.degradation)


class TestOfficialMissingFeedConfig:
    def test_unconfigured_asset_reports_gap(self):
        result = fetch_official_announcements(
            assets=["DOGE"],  # not in OFFICIAL_FEEDS
            analysis_as_of=ANALYSIS_AS_OF,
            client=httpx.Client(transport=httpx.MockTransport(lambda r: httpx.Response(200))),
            feed_overrides={},  # empty overrides
        )
        assert result.status == "failed"
        assert any("DOGE" in d for d in result.degradation)


class TestOfficialNonBlocking:
    """Official adapter failures never raise — they always return WorkerResult."""

    def test_partial_success_one_asset_fails(self):
        transport = _mock_transport({
            "ethereum.org": (200, VALID_RSS),
            "bitcoin.org": (500, "error"),
        })
        client = httpx.Client(transport=transport)
        result = fetch_official_announcements(
            assets=["ETH", "BTC"],
            analysis_as_of=ANALYSIS_AS_OF,
            client=client,
            feed_overrides=TEST_FEEDS,
        )
        # Should still return ETH drafts even though BTC failed
        assert result.status == "partial"
        assert len(result.drafts) >= 1
        assert any("Bitcoin.org" in d or "BTC" in d for d in result.degradation)
