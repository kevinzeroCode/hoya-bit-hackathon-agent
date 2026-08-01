"""Tests for the scripts/analyze.py entry point."""

from __future__ import annotations

import importlib.util
import sys
from datetime import date
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]  # from tests/unit/skills/
SCRIPT = REPO_ROOT / "scripts" / "analyze.py"


def _load_cli():
    spec = importlib.util.spec_from_file_location("analyze_cli", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    sys.modules["analyze_cli"] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def cli():
    return _load_cli()


def test_writes_both_formats_by_default(cli, tmp_path, capsys):
    assert cli.main(["BTC", "--out-dir", str(tmp_path)]) == 0

    written = sorted(p.name for p in tmp_path.iterdir())
    assert written == ["btc-analysis-2026-05-31.html", "btc-analysis-2026-05-31.md"]
    assert "wrote" in capsys.readouterr().out


def test_output_files_are_utf8_and_non_empty(cli, tmp_path):
    cli.main(["XRP", "--out-dir", str(tmp_path)])

    markdown = (tmp_path / "xrp-analysis-2026-05-31.md").read_text(encoding="utf-8")
    html = (tmp_path / "xrp-analysis-2026-05-31.html").read_text(encoding="utf-8")

    assert markdown.startswith("# XRP 價格資料分析")
    assert html.startswith("<!doctype html>")


def test_as_of_limits_the_series_and_names_the_file(cli, tmp_path):
    cli.main(["ETH", "--as-of", "2025-06-30", "--out-dir", str(tmp_path)])

    path = tmp_path / "eth-analysis-2025-06-30.md"
    assert path.exists()
    assert "2025-06-30" in path.read_text(encoding="utf-8")


def test_single_format_writes_only_that_file(cli, tmp_path):
    cli.main(["BNB", "--format", "html", "--out-dir", str(tmp_path)])

    assert [p.suffix for p in tmp_path.iterdir()] == [".html"]


def test_skill_subset_is_honoured(cli, tmp_path, capsys):
    cli.main(["BNB", "--skills", "A1,A3", "--out-dir", str(tmp_path)])

    out = capsys.readouterr().out
    assert "A1=" in out and "A3=" in out
    assert "A5=" not in out


def test_stdout_mode_writes_no_files(cli, tmp_path, capsys):
    assert cli.main(["BTC", "--out-dir", str(tmp_path), "--stdout"]) == 0

    assert list(tmp_path.iterdir()) == []
    assert "# BTC 價格資料分析" in capsys.readouterr().out


def test_status_line_reports_every_skill(cli, tmp_path, capsys):
    cli.main(["BTC", "--out-dir", str(tmp_path)])
    out = capsys.readouterr().out

    assert "A5=unavailable" in out  # BTC is the benchmark
    assert "A9=degraded" in out  # no research sources exist
    assert "bars=1826" in out


def test_unknown_asset_exits_nonzero_without_writing(cli, tmp_path, capsys):
    assert cli.main(["DOGE", "--out-dir", str(tmp_path)]) == 2

    assert list(tmp_path.iterdir()) == []
    assert "error:" in capsys.readouterr().err


def test_out_dir_is_created_when_missing(cli, tmp_path):
    target = tmp_path / "nested" / "deeper"
    cli.main(["BTC", "--out-dir", str(target)])

    assert target.is_dir()
    assert list(target.iterdir())


def test_asset_symbol_is_case_insensitive(cli, tmp_path):
    cli.main(["btc", "--out-dir", str(tmp_path)])

    assert (tmp_path / "btc-analysis-2026-05-31.md").exists()


@pytest.mark.parametrize("bad", ["2026-13-01", "31-05-2026", "yesterday"])
def test_invalid_date_is_rejected(cli, bad):
    with pytest.raises(SystemExit):
        cli.main(["BTC", "--as-of", bad])


def test_invalid_format_is_rejected(cli):
    with pytest.raises(SystemExit):
        cli.main(["BTC", "--format", "pdf"])


def test_invalid_skill_is_rejected(cli):
    with pytest.raises(SystemExit):
        cli.main(["BTC", "--skills", "A6"])


def test_date_parser_accepts_iso(cli):
    assert cli._parse_date("2026-05-31") == date(2026, 5, 31)


# --------------------------------------------------------------------------
# output naming and overwrite protection
# --------------------------------------------------------------------------

def test_custom_name_controls_the_filename(cli, tmp_path):
    cli.main(["BTC", "--name", "btc-run-7f3a", "--out-dir", str(tmp_path)])

    assert sorted(p.name for p in tmp_path.iterdir()) == [
        "btc-run-7f3a.html",
        "btc-run-7f3a.md",
    ]


def test_several_reports_of_one_asset_coexist_under_different_names(cli, tmp_path):
    """The point of --name: an agent producing many reports per asset."""
    for run_id in ("run-a", "run-b", "run-c"):
        assert cli.main(["BTC", "--name", run_id, "--format", "md", "--out-dir", str(tmp_path)]) == 0

    assert sorted(p.name for p in tmp_path.iterdir()) == ["run-a.md", "run-b.md", "run-c.md"]


def test_skill_subset_is_folded_into_the_default_name(cli, tmp_path):
    """A partial run must not land on the same file as a full run."""
    cli.main(["BTC", "--format", "md", "--out-dir", str(tmp_path)])
    cli.main(["BTC", "--skills", "A1", "--format", "md", "--out-dir", str(tmp_path)])

    assert sorted(p.name for p in tmp_path.iterdir()) == [
        "btc-analysis-2026-05-31-a1.md",
        "btc-analysis-2026-05-31.md",
    ]


def test_rerunning_the_same_command_refuses_to_overwrite(cli, tmp_path, capsys):
    assert cli.main(["BTC", "--format", "md", "--out-dir", str(tmp_path)]) == 0
    capsys.readouterr()

    assert cli.main(["BTC", "--format", "md", "--out-dir", str(tmp_path)]) == 3
    err = capsys.readouterr().err
    assert "refusing to overwrite" in err
    assert "--name" in err and "--force" in err


def test_force_allows_overwriting(cli, tmp_path):
    cli.main(["BTC", "--format", "md", "--out-dir", str(tmp_path)])
    assert cli.main(["BTC", "--format", "md", "--out-dir", str(tmp_path), "--force"]) == 0


def test_refusal_leaves_every_file_untouched(cli, tmp_path):
    """Targets are checked before any is written, so a refusal is atomic."""
    cli.main(["BTC", "--format", "md", "--out-dir", str(tmp_path)])
    markdown = tmp_path / "btc-analysis-2026-05-31.md"
    markdown.write_text("SENTINEL", encoding="utf-8")

    assert cli.main(["BTC", "--out-dir", str(tmp_path)]) == 3
    assert markdown.read_text(encoding="utf-8") == "SENTINEL"
    assert not (tmp_path / "btc-analysis-2026-05-31.html").exists()


def test_partial_collision_still_refuses(cli, tmp_path, capsys):
    """Only the .md exists; the run that would write both must still refuse."""
    cli.main(["BTC", "--format", "md", "--out-dir", str(tmp_path)])
    capsys.readouterr()

    assert cli.main(["BTC", "--out-dir", str(tmp_path)]) == 3
    assert ".md" in capsys.readouterr().err


@pytest.mark.parametrize("bad", ["../escape", "sub/dir", "a\\b", "report.md", "report.html", " "])
def test_unsafe_or_wrong_names_are_rejected(cli, bad):
    with pytest.raises(SystemExit):
        cli.main(["BTC", "--name", bad])


def test_name_cannot_write_outside_the_out_dir(cli, tmp_path):
    with pytest.raises(SystemExit):
        cli.main(["BTC", "--name", "../outside", "--out-dir", str(tmp_path)])

    assert not list(tmp_path.parent.glob("outside.*"))


def test_default_stem_helper(cli):
    from datetime import date

    from skills.report import SKILL_ORDER

    assert cli.default_stem("BTC", date(2026, 5, 31), SKILL_ORDER) == "btc-analysis-2026-05-31"
    assert cli.default_stem("BTC", date(2026, 5, 31), ("A1", "A3")) == "btc-analysis-2026-05-31-a1-a3"
    assert cli.default_stem("BTC", None, SKILL_ORDER) == "btc-analysis"


def test_cli_does_not_write_the_four_run_artifacts(cli, tmp_path):
    """This entry point must not appear to satisfy the artifact contract."""
    cli.main(["BTC", "--out-dir", str(tmp_path)])
    names = {p.name for p in tmp_path.iterdir()}

    assert names.isdisjoint(
        {"final_report.md", "evidence.json", "execution_log.jsonl", "run_config.json"}
    )
