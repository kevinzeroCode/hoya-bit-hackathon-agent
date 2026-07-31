# Crypto Data Source HTML Guide Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a self-contained Traditional Chinese `index.html` that documents HOYA BIT crypto data sources, safe API usage, UTC CSV rules, and evidence-based Agent constraints.

**Architecture:** The deliverable is one semantic HTML document with embedded CSS and progressive-enhancement JavaScript. A Python standard-library test file parses the document and enforces its content, security, accessibility, responsive, print, and interaction contracts without adding project dependencies.

**Tech Stack:** HTML5, embedded CSS, browser JavaScript, Python 3 `unittest` and `html.parser`

---

## File Structure

- Create: `index.html` — the complete offline-readable guide, styles, and interactions.
- Create: `tests/test_html_guide.py` — dependency-free structural and content contract tests.
- Reference: `docs/superpowers/specs/2026-07-30-crypto-data-source-html-design.md` — approved requirements and acceptance criteria.

### Task 1: Establish the semantic document contract

**Files:**
- Create: `tests/test_html_guide.py`
- Create: `index.html`

- [ ] **Step 1: Write the failing structure tests**

Create `tests/test_html_guide.py` with:

```python
from html.parser import HTMLParser
from pathlib import Path
import re
import unittest


ROOT = Path(__file__).resolve().parents[1]
HTML_PATH = ROOT / "index.html"

REQUIRED_SECTIONS = {
    "overview",
    "recommended-stack",
    "market-apis",
    "news",
    "social",
    "onchain",
    "pricing",
    "api-examples",
    "csv-standard",
    "agent-policy",
    "sources",
}


class GuideParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.section_ids = set()
        self.script_srcs = []
        self.stylesheet_hrefs = []
        self.links = []
        self.buttons = []
        self.in_main = False
        self.main_count = 0
        self.text_parts = []

    def handle_starttag(self, tag, attrs):
        values = dict(attrs)
        if tag == "main":
            self.in_main = True
            self.main_count += 1
        if tag == "section" and values.get("id"):
            self.section_ids.add(values["id"])
        if tag == "script" and values.get("src"):
            self.script_srcs.append(values["src"])
        if tag == "link" and values.get("rel") == "stylesheet":
            self.stylesheet_hrefs.append(values.get("href", ""))
        if tag == "a":
            self.links.append(values)
        if tag == "button":
            self.buttons.append(values)

    def handle_endtag(self, tag):
        if tag == "main":
            self.in_main = False

    def handle_data(self, data):
        self.text_parts.append(data)


class HtmlGuideTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.html = HTML_PATH.read_text(encoding="utf-8")
        cls.parser = GuideParser()
        cls.parser.feed(cls.html)
        cls.text = " ".join(" ".join(cls.parser.text_parts).split())

    def test_has_one_main_and_all_required_sections(self):
        self.assertEqual(self.parser.main_count, 1)
        self.assertEqual(REQUIRED_SECTIONS, self.parser.section_ids)

    def test_is_a_traditional_chinese_document(self):
        self.assertIn('lang="zh-Hant"', self.html)
        self.assertIn("HOYA BIT 加密市場資料來源指南", self.text)
        self.assertIn("非投資建議", self.text)

    def test_has_no_external_runtime_dependencies(self):
        self.assertEqual([], self.parser.script_srcs)
        self.assertEqual([], self.parser.stylesheet_hrefs)
        self.assertNotRegex(self.html, r"@import\s+url")

    def test_internal_navigation_targets_existing_sections(self):
        internal_targets = {
            link["href"][1:]
            for link in self.parser.links
            if link.get("href", "").startswith("#")
        }
        self.assertTrue(REQUIRED_SECTIONS.issubset(internal_targets))
        self.assertTrue(internal_targets.issubset(REQUIRED_SECTIONS))


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run the tests and verify the expected failure**

Run:

```powershell
python -m unittest tests.test_html_guide -v
```

Expected: `ERROR` with `FileNotFoundError` for `index.html`.

- [ ] **Step 3: Create the minimal semantic HTML shell**

Create `index.html` with a valid HTML5 document, `lang="zh-Hant"`, UTF-8 metadata, viewport metadata, a skip link, one `nav`, one `main`, and exactly these sections:

```html
<!doctype html>
<html lang="zh-Hant">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <meta name="description" content="HOYA BIT 加密市場資料來源、API 使用方法、UTC CSV 與 Agent 判斷限制指南">
  <title>HOYA BIT 加密市場資料來源指南</title>
  <style>
    html { scroll-behavior: smooth; }
  </style>
</head>
<body>
  <a href="#overview">跳至主要內容</a>
  <header>
    <p>HOYA BIT · DATA REFERENCE</p>
    <h1>HOYA BIT 加密市場資料來源指南</h1>
    <p>更新日期：2026-07-30</p>
    <p>本文件僅供研究與系統設計使用，並非投資建議。</p>
  </header>
  <nav aria-label="章節導覽">
    <a href="#overview">使用原則</a>
    <a href="#recommended-stack">建議組合</a>
    <a href="#market-apis">價格市場</a>
    <a href="#news">新聞公告</a>
    <a href="#social">社群情緒</a>
    <a href="#onchain">鏈上資料</a>
    <a href="#pricing">方案比較</a>
    <a href="#api-examples">API 範例</a>
    <a href="#csv-standard">CSV 規格</a>
    <a href="#agent-policy">Agent 限制</a>
    <a href="#sources">官方來源</a>
  </nav>
  <main>
    <section id="overview"><h2>使用原則</h2></section>
    <section id="recommended-stack"><h2>建議資料組合</h2></section>
    <section id="market-apis"><h2>價格與市場 API</h2></section>
    <section id="news"><h2>新聞與官方公告</h2></section>
    <section id="social"><h2>社群情緒</h2></section>
    <section id="onchain"><h2>鏈上資料</h2></section>
    <section id="pricing"><h2>免費與付費方案比較</h2></section>
    <section id="api-examples"><h2>API 使用範例</h2></section>
    <section id="csv-standard"><h2>UTC CSV 規格</h2></section>
    <section id="agent-policy"><h2>Agent 判斷流程與禁止事項</h2></section>
    <section id="sources"><h2>官方文件與來源</h2></section>
  </main>
</body>
</html>
```

- [ ] **Step 4: Run the structure tests**

Run:

```powershell
python -m unittest tests.test_html_guide -v
```

Expected: 4 tests pass.

- [ ] **Step 5: Commit the semantic shell**

```powershell
git add -- index.html tests/test_html_guide.py
git commit -m "test: define crypto data guide contract"
```

### Task 2: Add the verified data-source catalog

**Files:**
- Modify: `tests/test_html_guide.py`
- Modify: `index.html`

- [ ] **Step 1: Add failing catalog coverage tests**

Add these constants and tests inside `tests/test_html_guide.py`:

```python
REQUIRED_PROVIDERS = {
    "Binance",
    "OKX",
    "Coinbase",
    "CoinGecko",
    "CoinCap",
    "CoinMarketCap",
    "CoinDesk Data",
    "Yahoo Finance",
    "CryptoPanic",
    "CoinDesk RSS",
    "The Block",
    "Decrypt",
    "Reddit",
    "LunarCrush",
    "X API",
    "Etherscan V2",
    "BscScan",
    "Solscan",
    "Dune",
    "Glassnode",
    "Solana JSON-RPC",
}

REQUIRED_STATUS_LABELS = {"免費", "有限免費", "付費", "不建議作正式 API"}


def test_provider_catalog_is_complete(self):
    for provider in REQUIRED_PROVIDERS:
        with self.subTest(provider=provider):
            self.assertIn(provider, self.text)


def test_status_vocabulary_is_visible(self):
    for label in REQUIRED_STATUS_LABELS:
        self.assertIn(label, self.text)


def test_important_service_changes_are_disclosed(self):
    required_disclosures = (
        "CryptoCompare Min API 已 deprecated",
        "CoinDesk Data 免費 API 層已終止",
        "Yahoo Finance 沒有目前受支援的正式公開 Finance API",
        "Glassnode 免費帳戶不包含正式 API",
        "X API 採按使用量計費",
        "Solscan 的完整 API 主要是付費服務",
    )
    for disclosure in required_disclosures:
        self.assertIn(disclosure, self.text)
```

Move the three new methods into `HtmlGuideTest`.

- [ ] **Step 2: Verify the catalog tests fail**

Run:

```powershell
python -m unittest tests.test_html_guide.HtmlGuideTest.test_provider_catalog_is_complete tests.test_html_guide.HtmlGuideTest.test_important_service_changes_are_disclosed -v
```

Expected: failures naming absent providers and disclosures.

- [ ] **Step 3: Populate the overview and recommended stack**

In `#overview`, add:

- A definition that daily open means the first price in the 1-day candle beginning at `00:00:00 UTC` for one named venue and pair.
- A warning that `BTC-USD`, `BTC-USDT`, and cross-exchange aggregate prices are not interchangeable.
- A warning that third-party judgments, trading signals, and investment reports cannot be the primary conclusion.

In `#recommended-stack`, add a six-card grid with these exact roles:

| Role | Primary | Cross-check |
|---|---|---|
| UTC daily open | Binance `BTCUSDT` | OKX `BTC-USDT` |
| Actual USD pair | Coinbase `BTC-USD` | CoinGecko aggregate context |
| News | CryptoPanic | CoinDesk RSS, Decrypt RSS, official announcements |
| Social | Reddit | LunarCrush and X API when licensed |
| EVM on-chain | Etherscan V2 | BscScan and direct JSON-RPC |
| Solana/on-chain analytics | Solana JSON-RPC | Dune and paid Solscan |

- [ ] **Step 4: Populate all source sections**

Use semantic tables with `<caption>`, `<thead>`, and `<tbody>`. Every provider row must show access status, key requirement, recommended use, limitation, and an official HTTPS link.

The market table must include Binance, OKX, Coinbase, CoinGecko, CoinCap, CoinMarketCap, CoinDesk Data, and Yahoo Finance.

The news table must include CryptoPanic, CoinDesk RSS, The Block, Decrypt, and first-party Blog/RSS/GitHub Releases/governance/status pages.

The social table must include Reddit, LunarCrush, and X API.

The on-chain table must include Etherscan V2, BscScan, Solscan, Dune, Glassnode, Solana JSON-RPC, and direct Ethereum/BNB JSON-RPC.

Use these status assignments:

- `免費`: Binance, OKX, Coinbase public candles, publisher RSS, direct public RPC where available.
- `有限免費`: CoinGecko, CoinCap, CoinMarketCap, Reddit, Dune, Etherscan V2.
- `付費`: CoinDesk Data, The Block Pro API, LunarCrush social access, X API, Solscan Pro API, Glassnode API.
- `不建議作正式 API`: Yahoo Finance.

Add one visible “2026 重要變更” callout containing all six disclosure sentences asserted by the tests.

- [ ] **Step 5: Run the full catalog test suite**

Run:

```powershell
python -m unittest tests.test_html_guide -v
```

Expected: 7 tests pass.

- [ ] **Step 6: Commit the source catalog**

```powershell
git add -- index.html tests/test_html_guide.py
git commit -m "feat: document crypto data source catalog"
```

### Task 3: Add API, CSV, and Agent-policy guidance

**Files:**
- Modify: `tests/test_html_guide.py`
- Modify: `index.html`

- [ ] **Step 1: Write failing usage and policy tests**

Add these methods to `HtmlGuideTest`:

```python
def test_api_examples_cover_required_endpoints_and_utc_options(self):
    required_fragments = (
        "data-api.binance.vision/api/v3/klines",
        "interval=1d",
        "timeZone=0",
        "/api/v5/market/history-candles",
        "bar=1Dutc",
        "confirm=1",
        "api.coingecko.com/api/v3/coins/bitcoin/market_chart",
        "cryptopanic.com/api/developer/v2/posts",
        "api.etherscan.io/v2/api",
        "chainid=56",
    )
    for fragment in required_fragments:
        self.assertIn(fragment, self.html)

def test_csv_contract_is_documented(self):
    self.assertIn("date_utc,open", self.text)
    self.assertIn(
        "date_utc,asset,pair,venue,open,is_final,candle_open_utc,source,retrieved_at_utc",
        self.text,
    )
    self.assertIn("YYYY-MM-DDT00:00:00Z", self.text)
    self.assertIn("只輸出已完成的 UTC 日 K", self.text)

def test_agent_policy_rejects_third_party_signal_shortcuts(self):
    required_policy = (
        "不得直接作為主要分析結果",
        "至少兩種獨立資料類別",
        "Galaxy Score",
        "AltRank",
        "panic score",
        "自行計算",
        "原始資料",
        "多來源佐證",
    )
    for phrase in required_policy:
        self.assertIn(phrase, self.text)

def test_examples_use_placeholders_instead_of_embedded_secrets(self):
    self.assertIn("YOUR_API_KEY", self.html)
    self.assertIn("YOUR_AUTH_TOKEN", self.html)
    suspicious_assignments = re.findall(
        r"(?:api[_-]?key|auth[_-]?token)\s*[=:]\s*[\"']([^\"']+)[\"']",
        self.html,
        flags=re.IGNORECASE,
    )
    allowed = {"YOUR_API_KEY", "YOUR_AUTH_TOKEN"}
    self.assertTrue(set(suspicious_assignments).issubset(allowed))
```

- [ ] **Step 2: Verify the new tests fail**

Run:

```powershell
python -m unittest tests.test_html_guide.HtmlGuideTest.test_api_examples_cover_required_endpoints_and_utc_options tests.test_html_guide.HtmlGuideTest.test_csv_contract_is_documented tests.test_html_guide.HtmlGuideTest.test_agent_policy_rejects_third_party_signal_shortcuts -v
```

Expected: 3 failures for missing examples, CSV fields, and policy content.

- [ ] **Step 3: Add five copyable API examples**

Each example must use a heading, purpose paragraph, `<pre><code id="...">`, and a button with `data-copy-target`.

Use these exact request examples:

```text
GET https://data-api.binance.vision/api/v3/klines?symbol=BTCUSDT&interval=1d&timeZone=0&startTime=START_MS&endTime=END_MS&limit=1000

GET https://www.okx.com/api/v5/market/history-candles?instId=BTC-USDT&bar=1Dutc&limit=300
# 僅採用回傳陣列中 confirm=1 的已完成 K 線

GET https://api.coingecko.com/api/v3/coins/bitcoin/market_chart?vs_currency=usd&days=30&interval=daily

GET https://cryptopanic.com/api/developer/v2/posts/?auth_token=YOUR_AUTH_TOKEN&currencies=BTC,ETH&regions=en&kind=news&public=true

GET https://api.etherscan.io/v2/api?chainid=56&module=account&action=tokentx&address=ADDRESS&startblock=0&endblock=999999999&sort=asc&apikey=YOUR_API_KEY
```

Explain Binance response index `0=open time` and `1=open`; OKX response order `[ts,o,h,l,c,vol,volCcy,volCcyQuote,confirm]`; CoinGecko is aggregate context rather than the canonical venue open.

- [ ] **Step 4: Add CSV documentation**

Show both exact schemas:

```csv
date_utc,open
2026-07-29,12345.67
```

```csv
date_utc,asset,pair,venue,open,is_final,candle_open_utc,source,retrieved_at_utc
2026-07-29,BTC,BTCUSDT,Binance,12345.67,true,2026-07-29T00:00:00Z,Binance Spot API,2026-07-30T00:05:00Z
```

Label the numeric values as format examples rather than current market data. State `YYYY-MM-DDT00:00:00Z`, decimal-point formatting, source retention, and “只輸出已完成的 UTC 日 K”.

- [ ] **Step 5: Add the Agent evidence workflow**

Render six ordered stages:

1. 原始資料
2. UTC 正規化
3. 去重與驗證
4. 自行計算特徵
5. 多來源佐證
6. 結論與限制

Add explicit prohibited shortcut bullets for CryptoPanic `panic score`, LunarCrush `Galaxy Score` and `AltRank`, CoinCap TA, Glassnode Insights, Dune dashboard conclusions, and publisher investment analysis.

State that important conclusions require “至少兩種獨立資料類別” and that third-party outputs “不得直接作為主要分析結果”.

- [ ] **Step 6: Add official source links**

The final section must link directly to official documentation used by the guide. Include at least CoinGecko, Binance, OKX, Coinbase, CoinDesk Data, CryptoPanic, Reddit, LunarCrush, X, Etherscan, Solscan, Dune, Glassnode, and Solana docs.

All external anchors must include:

```html
target="_blank" rel="noopener noreferrer"
```

- [ ] **Step 7: Run tests and commit**

Run:

```powershell
python -m unittest tests.test_html_guide -v
```

Expected: 11 tests pass.

Commit:

```powershell
git add -- index.html tests/test_html_guide.py
git commit -m "feat: add API usage and evidence policy guide"
```

### Task 4: Implement responsive, print, accessibility, and copy behavior

**Files:**
- Modify: `tests/test_html_guide.py`
- Modify: `index.html`

- [ ] **Step 1: Add failing presentation and interaction tests**

Add these methods to `HtmlGuideTest`:

```python
def test_responsive_and_print_contracts_exist(self):
    self.assertRegex(self.html, r"@media\s*\(max-width:\s*900px\)")
    self.assertRegex(self.html, r"@media\s+print")
    self.assertIn("overflow-x: auto", self.html)
    self.assertIn("break-inside: avoid", self.html)

def test_copy_buttons_have_valid_targets(self):
    code_ids = set(re.findall(r"<code[^>]+id=[\"']([^\"']+)", self.html))
    targets = {
        button["data-copy-target"]
        for button in self.parser.buttons
        if button.get("data-copy-target")
    }
    self.assertGreaterEqual(len(targets), 7)
    self.assertTrue(targets.issubset(code_ids))

def test_javascript_is_progressive_and_private(self):
    self.assertIn("navigator.clipboard.writeText", self.html)
    self.assertIn("selectNodeContents", self.html)
    self.assertIn("IntersectionObserver", self.html)
    self.assertNotIn("localStorage", self.html)
    self.assertNotIn("document.cookie", self.html)

def test_external_links_are_safely_opened(self):
    external = [
        link for link in self.parser.links
        if link.get("href", "").startswith("https://")
    ]
    self.assertGreaterEqual(len(external), 14)
    for link in external:
        self.assertEqual("_blank", link.get("target"))
        self.assertEqual("noopener noreferrer", link.get("rel"))
```

- [ ] **Step 2: Verify the presentation tests fail**

Run:

```powershell
python -m unittest tests.test_html_guide.HtmlGuideTest.test_responsive_and_print_contracts_exist tests.test_html_guide.HtmlGuideTest.test_copy_buttons_have_valid_targets tests.test_html_guide.HtmlGuideTest.test_javascript_is_progressive_and_private -v
```

Expected: 3 failures for absent CSS and JavaScript behavior.

- [ ] **Step 3: Implement the visual system**

Replace the minimal `<style>` with embedded CSS that defines:

- Color custom properties for dark navy, cyan, green, amber, red, and muted text.
- A two-column desktop layout with a sticky navigation rail and readable content width.
- Cards for the recommended stack and status summaries.
- `table-wrap { overflow-x: auto; }` around every comparison table.
- Status badges that include text, not color alone.
- Code panels with a visible copy button and focus state.
- A pure CSS six-step workflow.
- `:focus-visible` outlines.
- `@media (max-width: 900px)` to convert navigation to a horizontally scrollable top rail and the main layout to one column.
- `@media print` to use white background, black text, hide navigation and copy buttons, show link destinations, and apply `break-inside: avoid` to cards, rows, and code examples.

Do not add a CSS import, remote font, image, or framework.

- [ ] **Step 4: Implement copy and active-section JavaScript**

Add this exact behavior at the end of `<body>`:

```html
<script>
  (() => {
    const status = document.querySelector("[data-copy-status]");

    function selectForManualCopy(element) {
      const range = document.createRange();
      range.selectNodeContents(element);
      const selection = window.getSelection();
      selection.removeAllRanges();
      selection.addRange(range);
      status.textContent = "無法自動複製，請按 Ctrl/Cmd+C 手動複製。";
    }

    document.querySelectorAll("[data-copy-target]").forEach((button) => {
      button.addEventListener("click", async () => {
        const target = document.getElementById(button.dataset.copyTarget);
        if (!target) return;

        try {
          await navigator.clipboard.writeText(target.textContent.trim());
          status.textContent = "已複製範例。";
          button.textContent = "已複製";
          window.setTimeout(() => {
            button.textContent = "複製";
            status.textContent = "";
          }, 1800);
        } catch (error) {
          selectForManualCopy(target);
        }
      });
    });

    if ("IntersectionObserver" in window) {
      const navLinks = new Map(
        [...document.querySelectorAll('nav a[href^="#"]')].map((link) => [
          link.getAttribute("href").slice(1),
          link,
        ])
      );
      const observer = new IntersectionObserver(
        (entries) => {
          entries
            .filter((entry) => entry.isIntersecting)
            .forEach((entry) => {
              navLinks.forEach((link) => link.removeAttribute("aria-current"));
              navLinks.get(entry.target.id)?.setAttribute("aria-current", "location");
            });
        },
        { rootMargin: "-20% 0px -70% 0px" }
      );
      document.querySelectorAll("main > section[id]").forEach((section) => {
        observer.observe(section);
      });
    }
  })();
</script>
```

Add one visually hidden live region:

```html
<p class="sr-only" aria-live="polite" data-copy-status></p>
```

- [ ] **Step 5: Run the complete automated suite**

Run:

```powershell
python -m unittest tests.test_html_guide -v
```

Expected: 15 tests pass.

- [ ] **Step 6: Commit presentation and interaction**

```powershell
git add -- index.html tests/test_html_guide.py
git commit -m "feat: style and enhance crypto data guide"
```

### Task 5: Final verification and handoff

**Files:**
- Verify: `index.html`
- Verify: `tests/test_html_guide.py`
- Verify: `docs/superpowers/specs/2026-07-30-crypto-data-source-html-design.md`

- [ ] **Step 1: Run the automated contract tests**

Run:

```powershell
python -m unittest tests.test_html_guide -v
```

Expected: 15 tests pass with `OK`.

- [ ] **Step 2: Check whitespace and repository scope**

Run:

```powershell
git diff --check
git status --short
```

Expected: no whitespace errors in `index.html` or `tests/test_html_guide.py`; only intended guide files are staged or modified by this implementation. Existing unrelated user changes remain untouched.

- [ ] **Step 3: Run a targeted secret scan**

Run:

```powershell
rg -n -i "(api[_-]?key|auth[_-]?token)\\s*[=:]\\s*['\\\"][^'\\\"]+['\\\"]" index.html
```

Expected: no real credential assignment; only `YOUR_API_KEY` and `YOUR_AUTH_TOKEN` may appear in documented URLs or code.

- [ ] **Step 4: Perform browser smoke checks**

Open `index.html` directly from disk and verify:

1. Desktop navigation remains visible while scrolling.
2. Every internal navigation link reaches the correct section.
3. Every copy button copies its own code block.
4. A narrow viewport below 900 px has no page-level horizontal overflow.
5. Tables scroll within their wrappers.
6. Print preview uses white background and hides navigation/copy controls.
7. With JavaScript disabled, all content and code examples remain readable.

- [ ] **Step 5: Record final evidence**

Capture the exact automated test result and note whether the direct-file, narrow-viewport, copy, print, and JavaScript-disabled checks passed. Do not claim visual verification that was not performed.

