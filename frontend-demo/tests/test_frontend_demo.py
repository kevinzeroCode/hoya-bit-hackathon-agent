from html.parser import HTMLParser
from pathlib import Path
import re
import unittest


ROOT = Path(__file__).resolve().parents[1]
HTML_PATH = ROOT / "index.html"
CSS_PATH = ROOT / "styles.css"


class DashboardParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.tags = []
        self.ids = set()
        self.text_parts = []
        self.external_urls = []

    def handle_starttag(self, tag, attrs):
        self.tags.append(tag)
        values = dict(attrs)
        if values.get("id"):
            self.ids.add(values["id"])
        for key in ("src", "href"):
            value = values.get(key, "")
            if value.startswith(("http://", "https://", "//")):
                self.external_urls.append(value)

    def handle_data(self, data):
        self.text_parts.append(data)


class FrontendDemoTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.html = HTML_PATH.read_text(encoding="utf-8")
        cls.parser = DashboardParser()
        cls.parser.feed(cls.html)
        cls.text = " ".join(cls.parser.text_parts)

    def test_semantic_dashboard_regions_exist(self):
        self.assertIn("header", self.parser.tags)
        self.assertIn("main", self.parser.tags)
        self.assertIn("footer", self.parser.tags)
        self.assertTrue(
            {"market-chart", "ai-summary", "risk-panel", "evidence-sources"}
            <= self.parser.ids
        )

    def test_demo_and_safety_labels_are_visible(self):
        for label in (
            "OFFLINE DEMO",
            "示範資料",
            "僅供研究與課堂展示",
            "不構成投資建議",
        ):
            self.assertIn(label, self.text)

    def test_page_has_no_external_resources(self):
        self.assertEqual([], self.parser.external_urls)
        self.assertNotIn("<script", self.html.lower())

    def test_static_chart_has_accessible_description(self):
        self.assertRegex(
            self.html,
            r'<svg[^>]+role="img"[^>]+aria-labelledby="chart-title chart-desc"',
        )
        self.assertIn('id="chart-title"', self.html)
        self.assertIn('id="chart-desc"', self.html)

    def test_stylesheet_contract(self):
        css = CSS_PATH.read_text(encoding="utf-8")
        self.assertIn("@media (max-width: 900px)", css)
        self.assertIn("@media (max-width: 600px)", css)
        self.assertIn("@media (prefers-reduced-motion: reduce)", css)
        self.assertIsNone(re.search(r"url\(\s*['\"]?https?://", css))


if __name__ == "__main__":
    unittest.main()
