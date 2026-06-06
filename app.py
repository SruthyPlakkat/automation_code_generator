"""Gradio UI for the Automation Code Generator agent."""

from __future__ import annotations

import base64
import re
import subprocess
import sys
import threading
import time

import gradio as gr
from dotenv import load_dotenv

from agent import run_agent

load_dotenv(override=True)

# Install Playwright's Chromium browser at startup (idempotent; required on HF Spaces)
subprocess.run(
    [sys.executable, "-m", "playwright", "install", "chromium"],
    check=False, capture_output=True,
)

# ── CSS ───────────────────────────────────────────────────────────────────────

CSS = """
/* ── Base (dark) ───────────────────────────────────────────────────────────── */
*, *::before, *::after { box-sizing: border-box; }

html { color-scheme: dark; }

body {
    font-family: 'Inter', 'Segoe UI', system-ui, sans-serif;
    background: linear-gradient(135deg, #0d0d1a 0%, #130d1f 45%, #0d1520 100%);
    min-height: 100vh;
    margin: 0;
}

/* ── Responsive container ──────────────────────────────────────────────────── */
.gradio-container {
    max-width: min(1600px, 96vw) !important;
    margin: 0 auto !important;
    padding: clamp(8px, 2vw, 24px) clamp(10px, 3vw, 32px) !important;
}

/* ── Animated header ───────────────────────────────────────────────────────── */
.app-header {
    background: linear-gradient(-45deg, #1e0544, #2d1060, #3b1375, #4c1d95, #2d1060);
    background-size: 400% 400%;
    animation: gradient-wave 10s ease infinite;
    border-radius: clamp(10px, 1.5vw, 18px);
    padding: clamp(16px, 3vw, 32px) clamp(20px, 4vw, 40px) clamp(14px, 2.5vw, 26px);
    margin-bottom: clamp(12px, 2vw, 22px);
    box-shadow: 0 8px 40px rgba(109, 40, 217, 0.4);
    border: 1px solid rgba(167, 139, 250, 0.2);
}
@keyframes gradient-wave {
    0%   { background-position: 0% 50%; }
    50%  { background-position: 100% 50%; }
    100% { background-position: 0% 50%; }
}
.app-header h1 {
    color: #ede9fe !important;
    margin: 0 0 8px;
    font-size: clamp(1.25rem, 2.8vw, 1.9rem);
    font-weight: 700;
    letter-spacing: -0.02em;
}
.app-header p {
    color: #c4b5fd !important;
    margin: 0 0 14px;
    font-size: clamp(0.8rem, 1.3vw, 0.95rem);
    line-height: 1.6;
    max-width: 680px;
}
.app-header .badges { display: flex; gap: 8px; flex-wrap: wrap; }
.app-header .badge {
    display: inline-flex;
    align-items: center;
    gap: 5px;
    background: rgba(255, 255, 255, 0.08);
    color: #ddd6fe;
    border-radius: 20px;
    padding: clamp(3px, 0.4vw, 5px) clamp(9px, 1.2vw, 14px);
    font-size: clamp(0.66rem, 0.9vw, 0.76rem);
    border: 1px solid rgba(167, 139, 250, 0.3);
    white-space: nowrap;
    font-weight: 500;
}

/* ── Step tracker ──────────────────────────────────────────────────────────── */
.steps-box {
    background: rgba(30, 20, 60, 0.7);
    border: 1px solid #3730a3;
    border-radius: 12px;
    padding: 12px 16px;
    box-shadow: 0 2px 12px rgba(109, 40, 217, 0.15);
}
.steps-title {
    font-size: 0.72rem;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    color: #a78bfa;
    margin-bottom: 10px;
}
.step-row {
    display: flex;
    align-items: center;
    gap: 10px;
    padding: 5px 0;
    font-size: clamp(0.8rem, 1.1vw, 0.88rem);
}
.step-dot {
    width: 10px;
    height: 10px;
    border-radius: 50%;
    flex-shrink: 0;
    transition: background 0.3s;
}
.dot-pending { background: #3730a3; }
.dot-active  { background: #7c3aed; animation: pulse-violet 1.4s ease-in-out infinite; }
.dot-done    { background: #a78bfa; }
@keyframes pulse-violet {
    0%,100% { box-shadow: 0 0 0 0 rgba(167, 139, 250, 0.6); }
    50%     { box-shadow: 0 0 0 7px rgba(167, 139, 250, 0); }
}

/* ── Chatbot ───────────────────────────────────────────────────────────────── */
.chatbot-wrap {
    border-radius: clamp(10px, 1.2vw, 14px) !important;
    overflow: hidden;
    box-shadow: 0 4px 28px rgba(109, 40, 217, 0.2) !important;
    border: 1px solid #3730a3 !important;
    background: #13111f !important;
}
.chatbot-wrap > .wrap,
.chatbot-wrap .bubble-wrap {
    min-height: 400px !important;
    max-height: 700px !important;
}
.chatbot-wrap pre, .chatbot-wrap .prose pre {
    background: #080810 !important;
    border: 1px solid #312e81 !important;
    border-radius: 10px !important;
    padding: clamp(10px, 1.5vw, 18px) clamp(12px, 1.8vw, 20px) !important;
    font-size: clamp(0.74rem, 0.95vw, 0.82rem) !important;
    max-height: 55vh !important;
    overflow-y: auto !important;
    line-height: 1.65 !important;
}
.chatbot-wrap code, .chatbot-wrap .prose code {
    font-family: 'Fira Code', 'JetBrains Mono', 'Cascadia Code', 'Consolas', monospace !important;
    font-size: clamp(0.74rem, 0.95vw, 0.82rem) !important;
    color: #c4b5fd !important;
}

/* ── Footer note ───────────────────────────────────────────────────────────── */
.footer-note {
    font-size: clamp(0.71rem, 0.95vw, 0.79rem);
    color: #7c3aed;
    margin-top: 12px;
    line-height: 1.9;
    border-top: 1px solid #312e81;
    padding-top: 12px;
    opacity: 0.85;
}

/* ── Responsive ────────────────────────────────────────────────────────────── */
@media (max-width: 640px) {
    .gradio-container { padding: 6px 8px !important; }
    .app-header { padding: 14px 16px 12px; }
}
"""

HEADER_HTML = """
<div class="app-header">
  <h1>🤖 Automation Code Generator</h1>
  <p>Provide a URL and describe what to test — the AI agent inspects the page
     and writes a complete, runnable Playwright pytest test script.</p>
  <div class="badges">
    <span class="badge">⚡ GPT-4o</span>
    <span class="badge">🎭 Playwright</span>
    <span class="badge">🧪 pytest</span>
  </div>
</div>
"""

WELCOME = [
    {
        "role": "assistant",
        "content": (
            "## 👋 Welcome!\n\n"
            "I'm an AI agent that turns any URL into a ready-to-run **Playwright test script**.\n\n"
            "**How it works:**\n"
            "1. 🌐 Navigate the page in a headless Chromium browser\n"
            "2. 🔍 Extract every interactive element with XPath & CSS selectors\n"
            "3. ✍️ Generate a complete `pytest-playwright` test script\n\n"
            "Enter a URL and test scenario on the left, then click **Generate Script** — "
            "or try one of the **Quick examples** to get started!"
        ),
    }
]

SPINNERS = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]

# ── Step tracker ──────────────────────────────────────────────────────────────

def _step_row(state: str, label: str) -> str:
    colours = {"pending": "#94a3b8", "active": "#3b82f6", "done": "#16a34a"}
    weight  = "600" if state != "pending" else "400"
    return (
        f'<div class="step-row">'
        f'<span class="step-dot dot-{state}"></span>'
        f'<span style="color:{colours[state]};font-weight:{weight}">{label}</span>'
        f'</div>'
    )

def _steps_html(status_log: list[str], done: bool = False) -> str:
    if not status_log and not done:
        return ""
    has_nav = any("navigat" in s.lower() for s in status_log)
    has_ext = any("extract" in s.lower() for s in status_log)

    if done:
        r1 = _step_row("done",    "✓ Page navigated")
        r2 = _step_row("done",    "✓ Elements extracted")
        r3 = _step_row("done",    "✓ Test script generated")
    elif has_ext:
        r1 = _step_row("done",    "✓ Page navigated")
        r2 = _step_row("done",    "✓ Elements extracted")
        r3 = _step_row("active",  "Generating test script…")
    elif has_nav:
        r1 = _step_row("done",    "✓ Page navigated")
        r2 = _step_row("active",  "Extracting elements…")
        r3 = _step_row("pending", "Generate test script")
    else:
        r1 = _step_row("active",  "Navigating to page…")
        r2 = _step_row("pending", "Extract page elements")
        r3 = _step_row("pending", "Generate test script")

    return (
        '<div class="steps-box">'
        '<div class="steps-title">Progress</div>'
        f'{r1}{r2}{r3}'
        '</div>'
    )


# ── Helpers ───────────────────────────────────────────────────────────────────

def _extract_code(text: str) -> str | None:
    m = re.search(r"```python\s*(.*?)```", text, re.DOTALL)
    return m.group(1).strip() if m else None


def _progress_msg(frame: str, status_log: list[str]) -> str:
    if not status_log:
        return f"{frame} **Launching headless browser…**\n\n_Starting Chromium…_"
    last = status_log[-1].lower()
    if "navigat" in last:
        return f"{frame} **Navigating to page…**\n\n_Loading DOM and capturing screenshot…_"
    if "extract" in last:
        return f"{frame} **Extracting page elements…**\n\n_Mapping XPaths, CSS selectors, ARIA labels…_"
    if "generat" in last:
        return f"{frame} **Generating test script…**\n\n_Analysing elements and writing assertions…_"
    return f"{frame} {status_log[-1]}"


def _validate_inputs(url: str, scenario: str) -> str | None:
    if not url.strip():
        return "Please enter a target URL."
    if not url.startswith(("http://", "https://")):
        return "URL must start with http:// or https://"
    if not scenario.strip():
        return "Please describe the test scenario."
    return None


# ── Generation handler ────────────────────────────────────────────────────────

def generate(
    url: str,
    scenario: str,
    chat_history: list[dict],
    agent_history: list[dict],
):
    def _out(chat, hist, interactive, btn_label, steps, dl):
        return (
            chat, hist,
            gr.update(interactive=interactive),
            gr.update(interactive=interactive),
            gr.update(value=btn_label, interactive=interactive),
            gr.update(value=steps),
            dl,
        )

    err = _validate_inputs(url, scenario)
    if err:
        yield _out(
            chat_history + [{"role": "assistant", "content": f"❌ **Error:** {err}"}],
            agent_history, True, "Generate Script", "", gr.update(value=""),
        )
        return

    user_msg = f"**🌐 URL**\n`{url}`\n\n**📋 Test Scenario**\n{scenario}"
    init_msg = f"{SPINNERS[0]} **Launching headless browser…**\n\n_Starting Chromium…_"

    chat_history = chat_history + [
        {"role": "user",      "content": user_msg},
        {"role": "assistant", "content": init_msg},
    ]
    yield _out(chat_history, agent_history, False, "⏳ Generating…",
               _steps_html([]), gr.update(value=""))

    status_log: list[str] = []
    result_holder: list = []
    start_time = time.time()

    def on_status(msg: str):
        status_log.append(msg)

    def worker():
        updated, text = run_agent(url, scenario, agent_history, on_status)
        result_holder.extend([updated, text])

    t = threading.Thread(target=worker, daemon=True)
    t.start()

    frame_idx = 0
    while t.is_alive():
        frame = SPINNERS[frame_idx % len(SPINNERS)]
        frame_idx += 1
        chat_history[-1] = {
            "role": "assistant",
            "content": _progress_msg(frame, status_log),
        }
        yield _out(chat_history, agent_history, False, "⏳ Generating…",
                   _steps_html(status_log), gr.update(value=""))
        t.join(timeout=1)

    if len(result_holder) < 2:
        chat_history[-1] = {
            "role": "assistant",
            "content": "❌ **Agent failed.** Check your `OPENAI_API_KEY` and network access.",
        }
        yield _out(chat_history, agent_history, True, "Generate Script",
                   "", gr.update(value=""))
        return

    elapsed = round(time.time() - start_time)
    new_history, final_text = result_holder

    code = _extract_code(final_text)
    footer = f"\n\n---\n*⏱ Completed in {elapsed}s*"
    if code:
        footer += f"  •  *{len(code.splitlines())} lines generated*"

    chat_history[-1] = {"role": "assistant", "content": final_text + footer}

    dl = gr.update(value="")
    if code:
        b64 = base64.b64encode(code.encode()).decode()
        dl = gr.update(
            value=(
                f'<a href="data:text/x-python;base64,{b64}" download="test_script.py"'
                ' style="display:inline-flex;align-items:center;gap:8px;padding:10px 22px;'
                'background:linear-gradient(135deg,#5b21b6,#7c3aed);color:#ede9fe;'
                'border-radius:10px;text-decoration:none;font-weight:600;font-size:0.9rem;'
                'border:1px solid rgba(167,139,250,0.4);box-shadow:0 2px 12px rgba(109,40,217,0.3);">'
                "⬇ Download test_script.py</a>"
            ),
        )

    yield _out(chat_history, new_history, True, "✨ Generate Script",
               _steps_html(status_log, done=True), dl)


def clear_all():
    return list(WELCOME), [], "", "", "", gr.update(value="")


# ── UI ─────────────────────────────────────────────────────────────────────────

EXAMPLE_SCENARIOS = [
    [
        "https://www.saucedemo.com",
        "Test the login flow with valid credentials (standard_user / secret_sauce) and verify "
        "the products page loads. Also test that an invalid login shows an error message.",
    ],
    [
        "https://www.google.com",
        "Test the search functionality: type a query, submit the form, and verify results appear.",
    ],
    [
        "https://the-internet.herokuapp.com/login",
        "Verify that valid credentials (tomsmith / SuperSecretPassword!) redirect to the secure "
        "area, and invalid credentials show an error.",
    ],
]

with gr.Blocks(title="Automation Code Generator") as demo:
    agent_history_state = gr.State([])

    gr.HTML(HEADER_HTML)

    # ── Top: URL + Scenario side-by-side ─────────────────────────────────────
    with gr.Row(equal_height=True):
        with gr.Column(scale=1, min_width=220):
            url_input = gr.Textbox(
                label="Target URL",
                placeholder="https://example.com",
                lines=1,
            )
        with gr.Column(scale=2, min_width=320):
            scenario_input = gr.Textbox(
                label="Test Scenario",
                placeholder=(
                    "Describe what to validate — e.g.:\n"
                    "• Test login with valid and invalid credentials\n"
                    "• Verify the checkout flow adds items to the cart\n"
                    "• Check that search returns relevant results"
                ),
                lines=4,
            )

    # ── Controls + progress ───────────────────────────────────────────────────
    with gr.Row(equal_height=True):
        with gr.Column(scale=1, min_width=160):
            generate_btn = gr.Button("Generate Script", variant="primary", size="lg")
        with gr.Column(scale=1, min_width=120):
            clear_btn = gr.Button("Clear", variant="secondary", size="lg")
        with gr.Column(scale=3, min_width=200):
            steps_html = gr.HTML(value="")

    # ── Quick examples ────────────────────────────────────────────────────────
    with gr.Accordion("Quick examples", open=False):
        gr.Examples(
            examples=EXAMPLE_SCENARIOS,
            inputs=[url_input, scenario_input],
            label="",
        )

    gr.HTML(
        '<div class="footer-note">'
        "🔑 Set <code>OPENAI_API_KEY</code> in <code>.env</code> &nbsp;|&nbsp; "
        "🌐 Playwright Chromium runs headless locally &nbsp;|&nbsp; "
        "⌨️ Press <kbd>Shift+Enter</kbd> in the scenario box to generate"
        "</div>"
    )

    # ── Bottom: full-width chatbot ────────────────────────────────────────────
    chatbot = gr.Chatbot(
        label="Generated Script & Analysis",
        value=list(WELCOME),
        height=600,
        elem_classes=["chatbot-wrap"],
    )
    download_btn = gr.HTML(value="")

    # ── Events ───────────────────────────────────────────────────────────────
    gen_outputs = [
        chatbot, agent_history_state,
        url_input, scenario_input,
        generate_btn,
        steps_html, download_btn,
    ]

    generate_btn.click(
        fn=generate,
        inputs=[url_input, scenario_input, chatbot, agent_history_state],
        outputs=gen_outputs,
    )
    scenario_input.submit(
        fn=generate,
        inputs=[url_input, scenario_input, chatbot, agent_history_state],
        outputs=gen_outputs,
    )
    clear_btn.click(
        fn=clear_all,
        outputs=[chatbot, agent_history_state, url_input, scenario_input, steps_html, download_btn],
    )


if __name__ == "__main__":
    demo.launch(
        server_name="0.0.0.0",
        server_port=7860,
        theme=gr.themes.Base(primary_hue="violet", secondary_hue="purple", neutral_hue="slate"),
        css=CSS,
        js="() => { document.documentElement.classList.add('dark'); }",
    )
