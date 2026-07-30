# Static Crypto Frontend Demo Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a dependency-free, presentation-ready HOYA BIT cryptocurrency research dashboard mockup that opens directly in a browser.

**Architecture:** A semantic `index.html` owns all visible Traditional Chinese content and an inline accessible SVG chart. A separate `styles.css` owns design tokens, the responsive dashboard layout, chart presentation, and reduced-motion behavior. A Python standard-library test parses both files and enforces the offline, semantic, responsive, and demo-label contracts.

**Tech Stack:** HTML5, CSS3, inline SVG, Python 3 `unittest`

---

## File Structure

- Create `frontend-demo/index.html`: semantic dashboard markup, mock market data,
  accessible static chart, AI summary, risk panel, evidence rows, and disclaimer.
- Create `frontend-demo/styles.css`: research-terminal design system, layouts,
  responsive breakpoints, focus/hover presentation, and reduced-motion rules.
- Create `frontend-demo/tests/test_frontend_demo.py`: deterministic structural and
  offline-contract tests using only the Python standard library.

### Task 1: Establish the offline HTML contract

**Files:**
- Create: `frontend-demo/tests/test_frontend_demo.py`
- Create: `frontend-demo/index.html`

- [ ] **Step 1: Write the failing structural tests**

Create `frontend-demo/tests/test_frontend_demo.py`:

```python
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
        self.assertIsNone(re.search(r"url\\(\\s*['\"]?https?://", css))


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run the tests and verify the expected failure**

Run:

```powershell
python -m unittest discover -s frontend-demo/tests -v
```

Expected: `ERROR` because `frontend-demo/index.html` does not exist.

- [ ] **Step 3: Create the complete semantic dashboard markup**

Create `frontend-demo/index.html` with:

```html
<!doctype html>
<html lang="zh-Hant">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <meta name="description" content="HOYA BIT 加密貨幣 AI 市場研究儀表板離線展示">
  <title>HOYA BIT — AI Crypto Market Intelligence</title>
  <link rel="stylesheet" href="./styles.css">
</head>
<body>
  <div class="ambient-grid" aria-hidden="true"></div>
  <header class="site-header">
    <a class="brand" href="#dashboard" aria-label="HOYA BIT 首頁">
      <span class="brand-mark" aria-hidden="true">H</span>
      <span><strong>HOYA BIT</strong><small>AI Crypto Market Intelligence</small></span>
    </a>
    <div class="header-meta">
      <span class="status-dot"><i aria-hidden="true"></i>系統展示正常</span>
      <span class="demo-badge">OFFLINE DEMO</span>
    </div>
  </header>

  <main id="dashboard" class="dashboard">
    <section class="hero" aria-labelledby="market-heading">
      <div>
        <p class="eyebrow">MARKET OVERVIEW · 示範資料</p>
        <h1 id="market-heading">Bitcoin <span>BTC / USD</span></h1>
        <div class="price-line">
          <strong>$67,842.16</strong>
          <span class="positive" aria-label="上漲 2.84%">↗ +2.84%</span>
        </div>
        <p class="timestamp">資料截至 2026-05-31 00:00 UTC · 非即時行情</p>
      </div>
      <dl class="metrics" aria-label="Bitcoin 市場摘要">
        <div><dt>24H HIGH</dt><dd>$69,124.80</dd></div>
        <div><dt>24H LOW</dt><dd>$65,907.34</dd></div>
        <div><dt>24H VOLUME</dt><dd>$38.6B</dd></div>
      </dl>
    </section>

    <section id="market-chart" class="panel chart-panel" aria-labelledby="chart-heading">
      <div class="panel-heading">
        <div><p class="eyebrow">PRICE ACTION</p><h2 id="chart-heading">BTC 30 日市場趨勢</h2></div>
        <span class="legend"><i aria-hidden="true"></i>收盤價</span>
      </div>
      <div class="chart-wrap">
        <svg viewBox="0 0 760 300" role="img" aria-labelledby="chart-title chart-desc">
          <title id="chart-title">BTC 三十日收盤價走勢</title>
          <desc id="chart-desc">示範走勢由約六萬三千美元震盪上升至六萬七千八百美元，期間曾短暫回落。</desc>
          <defs>
            <linearGradient id="area-fill" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stop-color="#42d9d0" stop-opacity=".28"/>
              <stop offset="100%" stop-color="#42d9d0" stop-opacity="0"/>
            </linearGradient>
          </defs>
          <g class="chart-grid" aria-hidden="true">
            <path d="M60 35H730 M60 95H730 M60 155H730 M60 215H730 M60 275H730"/>
            <path d="M60 35V275 M228 35V275 M395 35V275 M563 35V275 M730 35V275"/>
          </g>
          <path class="area" d="M60 235 C100 220 110 185 150 198 S220 170 260 182 S320 118 365 135 S420 155 460 112 S525 90 565 104 S630 55 675 76 S710 58 730 62 L730 275 L60 275 Z"/>
          <path class="line" d="M60 235 C100 220 110 185 150 198 S220 170 260 182 S320 118 365 135 S420 155 460 112 S525 90 565 104 S630 55 675 76 S710 58 730 62"/>
          <circle class="latest-point" cx="730" cy="62" r="5"/>
          <g class="chart-labels">
            <text x="8" y="40">$70K</text><text x="8" y="100">$68K</text>
            <text x="8" y="160">$66K</text><text x="8" y="220">$64K</text>
            <text x="8" y="280">$62K</text>
            <text x="60" y="298">05/01</text><text x="374" y="298">05/15</text>
            <text x="686" y="298">05/31</text>
          </g>
        </svg>
      </div>
      <p class="chart-note">圖表為課堂展示用靜態模擬資料，不代表即時或歷史報價。</p>
    </section>

    <aside id="ai-summary" class="panel insight-panel" aria-labelledby="ai-heading">
      <div class="panel-heading">
        <div><p class="eyebrow">AI RESEARCH BRIEF</p><h2 id="ai-heading">市場研究摘要</h2></div>
        <span class="confidence">信心程度 · 中</span>
      </div>
      <p class="lead">BTC 維持震盪偏多結構，但短期價格已接近近期壓力區，追價風險上升。</p>
      <ul class="insight-list">
        <li><span>01</span><p><strong>動能延續</strong>價格維持於短期均線上方，買方仍具主導權。</p></li>
        <li><span>02</span><p><strong>波動放大</strong>近期日內振幅提高，風險管理的重要性同步增加。</p></li>
        <li><span>03</span><p><strong>證據有限</strong>此頁使用離線示範資料，無法反映即時事件與鏈上資訊。</p></li>
      </ul>
      <div class="research-note">AI 摘要為介面示範，不是即時模型輸出。</div>
    </aside>

    <section id="risk-panel" class="panel risk-panel" aria-labelledby="risk-heading">
      <div class="panel-heading">
        <div><p class="eyebrow amber">RISK WATCH</p><h2 id="risk-heading">需要留意的風險</h2></div>
        <span class="risk-count">3 項</span>
      </div>
      <div class="risk-grid">
        <article><i aria-hidden="true">01</i><div><h3>波動率風險</h3><p>價格快速變動可能放大預期之外的損失。</p></div></article>
        <article><i aria-hidden="true">02</i><div><h3>動能反轉</h3><p>若跌破近期支撐，短期偏多結構可能失效。</p></div></article>
        <article><i aria-hidden="true">03</i><div><h3>資料時效</h3><p>離線示範未納入最新新聞、資金流與鏈上事件。</p></div></article>
      </div>
    </section>

    <section id="evidence-sources" class="panel evidence-panel" aria-labelledby="evidence-heading">
      <div class="panel-heading">
        <div><p class="eyebrow">EVIDENCE LEDGER</p><h2 id="evidence-heading">分析證據來源</h2></div>
        <span class="source-count">3 sources · 示範資料</span>
      </div>
      <div class="evidence-table" role="table" aria-label="示範證據來源">
        <div class="evidence-row evidence-head" role="row">
          <span role="columnheader">來源</span><span role="columnheader">摘要</span>
          <span role="columnheader">可靠度</span><span role="columnheader">時間</span>
        </div>
        <div class="evidence-row" role="row">
          <span role="cell"><b>MARKET</b>HOYA OHLCV Dataset</span>
          <span role="cell">BTC 日線價格與成交量</span><span role="cell"><em class="high">高</em></span>
          <span role="cell">2026-05-31</span>
        </div>
        <div class="evidence-row" role="row">
          <span role="cell"><b>TECHNICAL</b>Deterministic Metrics</span>
          <span role="cell">報酬率、均線與波動率</span><span role="cell"><em>中</em></span>
          <span role="cell">2026-05-31</span>
        </div>
        <div class="evidence-row" role="row">
          <span role="cell"><b>RESEARCH</b>Demo Research Note</span>
          <span role="cell">風險與限制條件說明</span><span role="cell"><em>中</em></span>
          <span role="cell">離線示範</span>
        </div>
      </div>
    </section>
  </main>

  <footer>
    <p>僅供研究與課堂展示，不構成投資建議</p>
    <span>HOYA BIT · STATIC DEMO v1.0</span>
  </footer>
</body>
</html>
```

- [ ] **Step 4: Run the HTML-focused tests**

Run:

```powershell
python frontend-demo/tests/test_frontend_demo.py FrontendDemoTests.test_semantic_dashboard_regions_exist FrontendDemoTests.test_demo_and_safety_labels_are_visible FrontendDemoTests.test_page_has_no_external_resources FrontendDemoTests.test_static_chart_has_accessible_description -v
```

Expected: four tests pass.

- [ ] **Step 5: Commit the semantic dashboard**

```powershell
git add -- frontend-demo/index.html frontend-demo/tests/test_frontend_demo.py
git commit -m "feat: add static crypto dashboard structure"
```

### Task 2: Apply the professional research-terminal presentation

**Files:**
- Create: `frontend-demo/styles.css`

- [ ] **Step 1: Run the stylesheet test and verify the expected failure**

Run:

```powershell
python frontend-demo/tests/test_frontend_demo.py FrontendDemoTests.test_stylesheet_contract -v
```

Expected: `ERROR` because `frontend-demo/styles.css` does not exist.

- [ ] **Step 2: Create the stylesheet**

Create `frontend-demo/styles.css` with:

```css
:root {
  color-scheme: dark;
  --bg: #071117;
  --panel: #0d1b22;
  --panel-strong: #10242c;
  --line: #1d3741;
  --text: #ecf5f5;
  --muted: #8ba3aa;
  --cyan: #42d9d0;
  --cyan-soft: #173e42;
  --green: #58df9b;
  --amber: #f4bd66;
  --red: #ff7e86;
  --radius: 18px;
  --shadow: 0 20px 60px rgb(0 0 0 / 22%);
}

* { box-sizing: border-box; }
html { scroll-behavior: smooth; }
body {
  margin: 0;
  min-width: 320px;
  background: radial-gradient(circle at 80% 0%, #12313a 0, transparent 34rem), var(--bg);
  color: var(--text);
  font-family: Inter, "Noto Sans TC", "Segoe UI", sans-serif;
  line-height: 1.55;
}
.ambient-grid {
  position: fixed;
  inset: 0;
  z-index: -1;
  opacity: .18;
  background-image: linear-gradient(#21404a 1px, transparent 1px), linear-gradient(90deg, #21404a 1px, transparent 1px);
  background-size: 64px 64px;
  mask-image: linear-gradient(to bottom, black, transparent 80%);
}
.site-header, .dashboard, footer { width: min(1180px, calc(100% - 40px)); margin-inline: auto; }
.site-header { min-height: 92px; display: flex; align-items: center; justify-content: space-between; border-bottom: 1px solid var(--line); }
.brand { display: flex; align-items: center; gap: 13px; color: var(--text); text-decoration: none; }
.brand-mark { width: 42px; aspect-ratio: 1; display: grid; place-items: center; border: 1px solid #41838a; border-radius: 12px; background: linear-gradient(145deg, #18434a, #0d2027); color: var(--cyan); font-weight: 900; }
.brand strong, .brand small { display: block; }
.brand strong { letter-spacing: .1em; }
.brand small { margin-top: 1px; color: var(--muted); font-size: .68rem; letter-spacing: .08em; }
.header-meta, .price-line, .panel-heading, .legend, .status-dot { display: flex; align-items: center; }
.header-meta { gap: 18px; color: var(--muted); font-size: .76rem; }
.status-dot { gap: 8px; }
.status-dot i, .legend i { display: inline-block; border-radius: 50%; background: var(--cyan); }
.status-dot i { width: 7px; height: 7px; box-shadow: 0 0 0 5px rgb(66 217 208 / 10%); }
.demo-badge, .confidence, .risk-count, .source-count { padding: 7px 10px; border: 1px solid var(--line); border-radius: 999px; background: #0a171d; color: var(--muted); font-size: .68rem; letter-spacing: .09em; }
.demo-badge { border-color: #39646b; color: var(--cyan); }
.dashboard { display: grid; grid-template-columns: minmax(0, 1.65fr) minmax(310px, .85fr); gap: 18px; padding-block: 34px; }
.hero { grid-column: 1 / -1; display: flex; align-items: end; justify-content: space-between; gap: 30px; padding: 22px 4px 14px; }
.eyebrow { margin: 0 0 9px; color: var(--cyan); font-size: .67rem; font-weight: 800; letter-spacing: .18em; }
.eyebrow.amber { color: var(--amber); }
h1, h2, h3, p { margin-top: 0; }
h1 { margin-bottom: 6px; font-size: clamp(1.6rem, 4vw, 2.5rem); letter-spacing: -.04em; }
h1 span { color: var(--muted); font-size: .86rem; font-weight: 500; letter-spacing: .05em; }
.price-line { gap: 15px; }
.price-line strong { font-size: clamp(2.2rem, 6vw, 4rem); line-height: 1; letter-spacing: -.055em; }
.positive { color: var(--green); font-weight: 750; }
.timestamp, .chart-note { margin: 12px 0 0; color: var(--muted); font-size: .72rem; }
.metrics { display: grid; grid-template-columns: repeat(3, minmax(115px, 1fr)); gap: 1px; margin: 0; overflow: hidden; border: 1px solid var(--line); border-radius: 14px; background: var(--line); }
.metrics div { padding: 14px 18px; background: #0a171d; }
.metrics dt { color: var(--muted); font-size: .6rem; letter-spacing: .12em; }
.metrics dd { margin: 5px 0 0; font-size: .95rem; font-weight: 700; }
.panel { border: 1px solid var(--line); border-radius: var(--radius); background: linear-gradient(145deg, rgb(17 37 45 / 96%), rgb(10 24 30 / 96%)); box-shadow: var(--shadow); }
.chart-panel, .insight-panel, .risk-panel, .evidence-panel { padding: 24px; }
.panel-heading { justify-content: space-between; gap: 16px; margin-bottom: 20px; }
.panel-heading h2 { margin: 0; font-size: 1.04rem; letter-spacing: -.01em; }
.legend { gap: 7px; color: var(--muted); font-size: .7rem; }
.legend i { width: 7px; height: 7px; }
.chart-wrap { min-height: 300px; }
.chart-wrap svg { display: block; width: 100%; height: auto; overflow: visible; }
.chart-grid path { fill: none; stroke: #23404a; stroke-width: 1; }
.area { fill: url(#area-fill); }
.line { fill: none; stroke: var(--cyan); stroke-width: 3; stroke-linecap: round; }
.latest-point { fill: var(--cyan); stroke: #d7fffc; stroke-width: 3; }
.chart-labels { fill: #728d95; font-size: 10px; }
.confidence { border-color: #35726f; color: var(--cyan); }
.lead { margin-bottom: 22px; color: #d9e8e9; font-size: 1.05rem; font-weight: 620; line-height: 1.65; }
.insight-list { display: grid; gap: 13px; margin: 0; padding: 0; list-style: none; }
.insight-list li { display: grid; grid-template-columns: 32px 1fr; gap: 10px; padding-top: 13px; border-top: 1px solid var(--line); }
.insight-list li > span { color: #51717a; font-family: ui-monospace, monospace; font-size: .75rem; }
.insight-list p { margin: 0; color: var(--muted); font-size: .82rem; }
.insight-list strong { display: block; margin-bottom: 2px; color: var(--text); }
.research-note { margin-top: 18px; padding: 10px 12px; border-left: 2px solid var(--cyan); background: var(--cyan-soft); color: #b5d5d5; font-size: .72rem; }
.risk-panel, .evidence-panel { grid-column: 1 / -1; }
.risk-count { color: var(--amber); }
.risk-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 12px; }
.risk-grid article { display: flex; gap: 14px; padding: 16px; border: 1px solid #4a3b28; border-radius: 12px; background: rgb(244 189 102 / 5%); }
.risk-grid i { color: var(--amber); font-family: ui-monospace, monospace; font-size: .72rem; font-style: normal; }
.risk-grid h3 { margin-bottom: 4px; font-size: .86rem; }
.risk-grid p { margin: 0; color: var(--muted); font-size: .76rem; }
.evidence-table { overflow: hidden; border: 1px solid var(--line); border-radius: 12px; }
.evidence-row { display: grid; grid-template-columns: 1.1fr 1.5fr .5fr .65fr; gap: 16px; align-items: center; padding: 13px 16px; border-top: 1px solid var(--line); color: var(--muted); font-size: .76rem; }
.evidence-row:first-child { border-top: 0; }
.evidence-head { background: #0a171d; color: #68848c; font-size: .6rem; font-weight: 800; letter-spacing: .12em; }
.evidence-row b { display: block; margin-bottom: 2px; color: var(--cyan); font-size: .56rem; letter-spacing: .12em; }
.evidence-row em { color: var(--amber); font-style: normal; }
.evidence-row em.high { color: var(--green); }
footer { display: flex; justify-content: space-between; gap: 20px; padding-block: 24px 40px; border-top: 1px solid var(--line); color: var(--muted); font-size: .7rem; }
footer p { margin: 0; color: #bfd0d2; }

@media (max-width: 900px) {
  .dashboard { grid-template-columns: 1fr; }
  .hero { align-items: start; flex-direction: column; }
  .insight-panel, .chart-panel { grid-column: 1; }
  .risk-grid { grid-template-columns: 1fr; }
}

@media (max-width: 600px) {
  .site-header, .dashboard, footer { width: min(100% - 24px, 1180px); }
  .site-header { min-height: 78px; }
  .brand small, .status-dot { display: none; }
  .dashboard { gap: 12px; padding-block: 18px; }
  .hero { padding-top: 12px; }
  .price-line { align-items: flex-start; flex-direction: column; gap: 4px; }
  .metrics { width: 100%; overflow-x: auto; }
  .metrics div { min-width: 118px; padding-inline: 12px; }
  .chart-panel, .insight-panel, .risk-panel, .evidence-panel { padding: 17px; }
  .chart-wrap { min-height: 180px; overflow-x: auto; }
  .chart-wrap svg { min-width: 600px; }
  .evidence-table { overflow-x: auto; }
  .evidence-row { min-width: 680px; }
  footer { align-items: flex-start; flex-direction: column; }
}

@media (prefers-reduced-motion: reduce) {
  html { scroll-behavior: auto; }
  *, *::before, *::after { transition-duration: .01ms !important; }
}
```

- [ ] **Step 3: Run all tests**

Run:

```powershell
python -m unittest discover -s frontend-demo/tests -v
```

Expected: `Ran 5 tests` and `OK`.

- [ ] **Step 4: Commit the visual design**

```powershell
git add -- frontend-demo/styles.css
git commit -m "feat: style crypto research dashboard"
```

### Task 3: Validate presentation readiness

**Files:**
- Verify: `frontend-demo/index.html`
- Verify: `frontend-demo/styles.css`
- Verify: `frontend-demo/tests/test_frontend_demo.py`

- [ ] **Step 1: Run the complete deterministic test suite**

Run:

```powershell
python -m unittest discover -s frontend-demo/tests -v
```

Expected: all five tests pass.

- [ ] **Step 2: Scan for accidental external resources or unfinished copy**

Run:

```powershell
rg -n "https?://|TODO|TBD|PLACEHOLDER" frontend-demo
```

Expected: no matches.

- [ ] **Step 3: Check the final Git diff for whitespace errors**

Run:

```powershell
git diff --check HEAD~2..HEAD -- frontend-demo
```

Expected: no output.

- [ ] **Step 4: Inspect the page at target viewport widths**

Open `frontend-demo/index.html` in a local browser and inspect at:

- 1440 × 1000: chart and AI summary appear side by side.
- 768 × 1024: content is one column with no clipped text.
- 375 × 812: metrics, chart, and evidence table remain deliberately scrollable
  without forcing the whole page wider than the viewport.

Expected: no overlapping content, missing text, missing styles, or network
dependency. The `OFFLINE DEMO`, data timestamp, demo labels, and investment
disclaimer are visible.

- [ ] **Step 5: Record final status**

Run:

```powershell
git status --short
```

Expected: `frontend-demo/` has no uncommitted changes. Pre-existing unrelated
working-tree changes may remain and must not be modified or committed.
