"""Tests for prompt loading and for the content contract of the shipped prompts.

The content assertions are deliberate: the prompts are the only place where the
bounded-reasoning rules are stated to the model, so silently deleting one of
those rules should fail the build.
"""

from __future__ import annotations

import unittest

from hoya_agent.reasoning.prompt_library import (
    PROMPT_FILES,
    Prompt,
    PromptError,
    load_prompt,
    parse_prompt,
    prompt_versions,
)

VALID = """---
prompt_id: demo
version: v3
language: zh-Hant
---

第一行內容。

第二段。
"""


class ParsingTests(unittest.TestCase):
    def test_parses_metadata_and_body(self):
        prompt = parse_prompt(VALID)
        self.assertEqual(prompt.prompt_id, "demo")
        self.assertEqual(prompt.version, "v3")
        self.assertEqual(prompt.metadata["language"], "zh-Hant")
        self.assertTrue(prompt.body.startswith("第一行內容。"))
        self.assertNotIn("prompt_id", prompt.body, "frontmatter must not leak")

    def test_version_label_is_stable(self):
        self.assertEqual(parse_prompt(VALID).version_label, "demo-v3")

    def test_missing_opening_fence_is_rejected(self):
        with self.assertRaises(PromptError):
            parse_prompt("prompt_id: demo\nversion: v1\n\nbody")

    def test_missing_closing_fence_is_rejected(self):
        with self.assertRaises(PromptError):
            parse_prompt("---\nprompt_id: demo\nversion: v1\n\nbody")

    def test_missing_version_is_rejected(self):
        with self.assertRaises(PromptError):
            parse_prompt("---\nprompt_id: demo\n---\n\nbody")

    def test_missing_prompt_id_is_rejected(self):
        with self.assertRaises(PromptError):
            parse_prompt("---\nversion: v1\n---\n\nbody")

    def test_empty_body_is_rejected(self):
        with self.assertRaises(PromptError):
            parse_prompt("---\nprompt_id: demo\nversion: v1\n---\n\n   \n")

    def test_malformed_frontmatter_line_is_rejected(self):
        with self.assertRaises(PromptError):
            parse_prompt("---\nprompt_id demo\nversion: v1\n---\n\nbody")


class LoadingTests(unittest.TestCase):
    def test_every_registered_stage_loads(self):
        for stage in PROMPT_FILES:
            with self.subTest(stage=stage):
                self.assertIsInstance(load_prompt(stage), Prompt)

    def test_unknown_stage_is_rejected(self):
        with self.assertRaises(PromptError):
            load_prompt("nope")

    def test_prompt_versions_covers_every_stage(self):
        versions = prompt_versions()
        self.assertEqual(set(versions), set(PROMPT_FILES))
        self.assertEqual(versions["arbiter"], "arbiter-v1")
        self.assertEqual(versions["planner"], "planner-v1")
        self.assertEqual(versions["research_extraction"], "research-extraction-v1")


class SharedPromptContractTests(unittest.TestCase):
    """Rules every bounded-reasoning prompt must state."""

    def setUp(self):
        self.prompts = {stage: load_prompt(stage) for stage in PROMPT_FILES}

    def test_reports_are_traditional_chinese(self):
        for stage, prompt in self.prompts.items():
            with self.subTest(stage=stage):
                self.assertEqual(prompt.metadata.get("language"), "zh-Hant")

    def test_every_prompt_resists_prompt_injection(self):
        for stage, prompt in self.prompts.items():
            with self.subTest(stage=stage):
                self.assertIn("忽略", prompt.body)
                self.assertIn("指令", prompt.body)

    def test_every_prompt_forbids_investment_advice(self):
        for stage, prompt in self.prompts.items():
            with self.subTest(stage=stage):
                self.assertIn("投資建議", prompt.body)

    def test_every_prompt_forbids_non_json_output(self):
        for stage, prompt in self.prompts.items():
            with self.subTest(stage=stage):
                self.assertIn("JSON 以外", prompt.body)


class ArbiterPromptContractTests(unittest.TestCase):
    def setUp(self):
        self.body = load_prompt("arbiter").body

    def test_states_the_claim_layering(self):
        for token in ("fact", "inference", "conclusion", "based_on_claim_ids"):
            self.assertIn(token, self.body)

    def test_states_the_stance_enum_and_its_location(self):
        for token in ("supports", "opposes", "neutral"):
            self.assertIn(token, self.body)
        self.assertIn("stance 只存在於 link", self.body)

    def test_states_the_confidence_caps(self):
        self.assertIn("insufficient_data", self.body)
        self.assertIn("獨立群", self.body)
        self.assertIn("confidence_rationale", self.body)

    def test_forbids_numeric_probability(self):
        self.assertIn("機率", self.body)

    def test_requires_counter_evidence_handling(self):
        self.assertIn("反方證據", self.body)

    def test_states_the_quantified_invalidation_contract(self):
        for token in ("basis_evidence_id", "threshold", "lt", "gte"):
            self.assertIn(token, self.body)
        self.assertIn("不得自己算", self.body)

    def test_forbids_minting_market_numbers(self):
        self.assertIn("不得自創任何市場數值", self.body)


class PlannerPromptContractTests(unittest.TestCase):
    def setUp(self):
        self.body = load_prompt("planner").body

    def test_restricts_tools_to_the_allowlist(self):
        self.assertIn("available_operations", self.body)
        self.assertIn("允許清單", self.body)

    def test_forbids_market_judgement(self):
        self.assertIn("不得給出任何市場判斷", self.body)

    def test_states_the_asset_mismatch_rule(self):
        self.assertIn("asset_question_mismatch_warning", self.body)
        self.assertIn("以 `assets` 為準", self.body)


class ResearchExtractionPromptContractTests(unittest.TestCase):
    def setUp(self):
        self.body = load_prompt("research_extraction").body

    def test_forbids_inventing_facts_and_numbers(self):
        self.assertIn("不得產生原始紀錄中不存在的事實", self.body)
        self.assertIn("不得自行計算或估算數值", self.body)

    def test_forbids_fabricating_timestamps(self):
        self.assertIn("published_at", self.body)
        self.assertIn("絕不以抓取時間冒充發布時間", self.body)

    def test_leaves_reliability_to_deterministic_policy(self):
        self.assertIn("reliability", self.body)
        self.assertIn("independence_group", self.body)


if __name__ == "__main__":
    unittest.main()
