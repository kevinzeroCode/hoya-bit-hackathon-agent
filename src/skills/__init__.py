"""Analysis skills for the HOYA market agent.

Each skill turns prepared OHLCV data into one ``SkillResult``: structured
findings, the provenance behind them, what could not be determined, and a
ready-to-render Traditional Chinese section.

All of it is deterministic -- no skill calls a model, and no number in a
report section originates anywhere but a calculation in ``calc``.

Typical use::

    from skills.dataset import load_bundle
    from skills.report import build_report

    bundle, load_report = load_bundle("HOYA_BIT_crypto_market_dataset/data", "BTC")
    report = build_report(bundle)
    print(report.markdown)

Individual skills can also be run alone::

    from skills import a1_regime
    result = a1_regime.run(bundle)
"""

from . import (
    a1_regime,
    a2_position,
    a3_risk,
    a4_participation,
    a5_attribution,
    a7_analogs,
    a9_verification,
)
from .base import (
    DEGRADED,
    OK,
    UNAVAILABLE,
    EvidenceRef,
    MarketBundle,
    SkillResult,
)
from .dataset import DatasetError, LoadReport, load_bundle
from .lint import ProhibitedAdviceError, assert_no_advice, find_prohibited_terms
from .report import SKILL_ORDER, AnalysisReport, build_report, render_report, run_skills

__all__ = [
    "DEGRADED",
    "OK",
    "SKILL_ORDER",
    "UNAVAILABLE",
    "AnalysisReport",
    "DatasetError",
    "EvidenceRef",
    "LoadReport",
    "MarketBundle",
    "ProhibitedAdviceError",
    "SkillResult",
    "a1_regime",
    "a2_position",
    "a3_risk",
    "a4_participation",
    "a5_attribution",
    "a7_analogs",
    "a9_verification",
    "assert_no_advice",
    "build_report",
    "find_prohibited_terms",
    "load_bundle",
    "render_report",
    "run_skills",
]
