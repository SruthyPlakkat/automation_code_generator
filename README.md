# Automation Code Generator

An AI agent that accepts a URL and a plain-English test scenario, then automatically:

1. **Navigates** the target URL in a headless Chromium browser
2. **Extracts** every interactive element (inputs, buttons, links, selects…) with its XPath, CSS selector, `id`, `name`, `aria-label`, `data-testid`, and visible text
3. **Generates** a complete, runnable [Playwright](https://playwright.dev/python/) pytest script

---

## Architecture

```
app.py          ← Gradio web UI
agent.py        ← Claude tool-use agentic loop (orchestrator)
tools.py        ← Playwright-based tools (navigate_and_capture, extract_page_elements)
```

### How the agent loop works

```
User (URL + scenario)
       │
       ▼
  Claude (claude-sonnet-4-6)
       │  calls tool ──► navigate_and_capture(url)
       │                  → title, URL, HTML snippet
       │  calls tool ──► extract_page_elements(url)
       │                  → list of elements + selectors
       │
       ▼
  Claude generates Playwright pytest script
       │
       ▼
  Gradio UI displays analysis + code
```

---

## API Keys Required

| Key | Where to get it | Required? |
|-----|----------------|-----------|
| `ANTHROPIC_API_KEY` | [console.anthropic.com](https://console.anthropic.com/settings/keys) | ✅ Yes |

No other API keys are needed — Playwright runs locally via headless Chromium.

---

## Setup & Run

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Install Playwright's Chromium browser (one-time)
playwright install chromium

# 3. Add your Anthropic API key
echo "ANTHROPIC_API_KEY=sk-ant-..." > .env

# 4. Launch the app
python app.py
# → Open http://localhost:7860
```

Or using `uv`:

```bash
uv run python app.py
```

---

## Running the Generated Tests

The agent outputs a `pytest-playwright` script. To run it:

```bash
pip install pytest pytest-playwright
playwright install chromium

# Save the generated script, e.g. test_login.py, then:
pytest test_login.py -v
```

---

## Example Scenarios

| URL | Scenario |
|-----|----------|
| `https://www.saucedemo.com` | Login with valid/invalid credentials, verify product page |
| `https://the-internet.herokuapp.com/login` | Form validation — correct and incorrect credentials |
| `https://www.google.com` | Search flow — type a query, verify results appear |

---

## Limitations

- JavaScript-heavy SPAs may need extra `wait_for_selector` calls in the generated script
- Pages behind authentication cannot be inspected without credentials
- Generated selectors are based on the public DOM — `data-testid` attributes (if present) produce the most stable tests
