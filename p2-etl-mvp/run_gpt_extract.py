"""Run ONE real GPT extraction end-to-end.

Requires: `pip install openai` and the OPENAI_API_KEY environment variable set.
This makes a real (paid) OpenAI API call. Usage:  python run_gpt_extract.py
"""

from __future__ import annotations

from datetime import datetime, timezone

from reasoning.gpt_client import GptClient
from reasoning.research_extractor import NewsRecord, extract_news_facts


def main() -> None:
    records = [
        NewsRecord(
            asset="BTC",
            title="Bitcoin ETF sees record inflows",
            body="Spot bitcoin ETFs recorded their largest single-day net inflow "
            "since launch, according to issuer filings. Analysts note the surge "
            "coincided with renewed institutional demand.",
            source_name="CoinDesk",
            publisher_domain="coindesk.com",
            source_url="https://cryptopanic.com/news/1",
            published_at=datetime(2026, 5, 30, 12, 0, tzinfo=timezone.utc),
        )
    ]
    print("呼叫 GPT 抽取中...(真 API)")
    result = extract_news_facts(records, llm=GptClient())
    print(f"狀態：{result.status}｜抽取證據筆數：{len(result.drafts)}")
    for d in result.drafts:
        print(f"  - [{d.reliability}] {d.normalized_fact}")
        print(f"      來源={d.source_name} 獨立群={d.independence_group} "
              f"prompt={d.query_or_parameters}")
    if result.degradation:
        print(f"降級揭露：{result.degradation}")


if __name__ == "__main__":
    main()
