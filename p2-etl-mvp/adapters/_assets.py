"""Coin-agnostic asset -> mention-terms map, shared by keyword-filtering adapters."""

from __future__ import annotations

ASSET_TERMS: dict[str, tuple[str, ...]] = {
    "BTC": ("btc", "bitcoin"),
    "ETH": ("eth", "ethereum"),
    "SOL": ("sol", "solana"),
    "BNB": ("bnb", "binance coin", "binancecoin"),
    "XRP": ("xrp", "ripple"),
}


def mentions(asset: str, text: str) -> bool:
    terms = ASSET_TERMS.get(asset)
    if terms is None:
        raise ValueError(f"unsupported asset: {asset}")
    low = text.lower()
    return any(t in low for t in terms)
