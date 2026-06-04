"""Gradio UI for the Automation Code Generator agent."""

from __future__ import annotations

import threading
import gradio as gr
from dotenv import load_dotenv

from agent import run_agent

load_dotenv(override=True)

# ── Helpers ──────────────────────────────────────────────────────────────────

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
    err = _validate_inputs(url, scenario)
    if err:
        yield (
            chat_history + [{"role": "assistant", "content": f"**Error:** {err}"}],
            agent_history,
            gr.update(interactive=True),
            gr.update(interactive=True),
            gr.update(interactive=True),
            gr.update(value="Generate Script", interactive=True),
        )
        return

    # Show the user's request immediately
    user_msg = f"**URL:** {url}\n\n**Test Scenario:** {scenario}"
    chat_history = chat_history + [{"role": "user", "content": user_msg}]
    thinking_msg = (
        "Launching headless browser to inspect the page...\n\n"
        "_This may take 15-30 seconds while I navigate the URL and extract elements._"
    )
    chat_history = chat_history + [{"role": "assistant", "content": thinking_msg}]

    yield (
        chat_history,
        agent_history,
        gr.update(interactive=False),
        gr.update(interactive=False),
        gr.update(interactive=False),
        gr.update(value="Generating…", interactive=False),
    )

    # Status messages collected from the agent loop
    status_log: list[str] = []

    def on_status(msg: str):
        status_log.append(msg)

    # Run agent in a thread so we can yield status updates
    result_holder: list = []

    def worker():
        updated_hist, text = run_agent(url, scenario, agent_history, on_status)
        result_holder.extend([updated_hist, text])

    t = threading.Thread(target=worker, daemon=True)
    t.start()

    # Poll and stream status updates while agent runs
    while t.is_alive():
        if status_log:
            progress = "\n".join(f"- {s}" for s in status_log)
            interim = (
                f"**Progress:**\n{progress}\n\n"
                "_Still working — generating your test script..._"
            )
            chat_history[-1] = {"role": "assistant", "content": interim}
            yield (
                chat_history,
                agent_history,
                gr.update(interactive=False),
                gr.update(interactive=False),
                gr.update(interactive=False),
                gr.update(value="Generating…", interactive=False),
            )
        t.join(timeout=1)

    if len(result_holder) < 2:
        chat_history[-1] = {
            "role": "assistant",
            "content": "**Error:** Agent failed to produce a response. Check your API key and network access.",
        }
        yield (
            chat_history,
            agent_history,
            gr.update(interactive=True),
            gr.update(interactive=True),
            gr.update(interactive=True),
            gr.update(value="Generate Script", interactive=True),
        )
        return

    new_agent_history, final_text = result_holder
    chat_history[-1] = {"role": "assistant", "content": final_text}

    yield (
        chat_history,
        new_agent_history,
        gr.update(interactive=True),
        gr.update(interactive=True),
        gr.update(interactive=True),
        gr.update(value="Generate Script", interactive=True),
    )


def clear_all():
    return [], [], "", ""


# ── UI ────────────────────────────────────────────────────────────────────────

DESCRIPTION = """\
## Automation Code Generator
Provide a URL and describe what you want to test. The agent will:
1. Open the page in a headless Chromium browser
2. Capture a screenshot and extract every interactive element with its XPath / CSS selector
3. Generate a complete, runnable **Playwright (Python)** test script
"""

EXAMPLE_SCENARIOS = [
    ["https://www.saucedemo.com", "Test the login flow with valid credentials (standard_user / secret_sauce) and verify the products page loads. Also test that an invalid login shows an error message."],
    ["https://www.google.com", "Test the search functionality: type a query, submit the form, and verify results appear with a headline."],
    ["https://the-internet.herokuapp.com/login", "Verify that logging in with valid credentials (tomsmith / SuperSecretPassword!) redirects to the secure area, and invalid credentials show an error."],
]

with gr.Blocks(
    title="Automation Code Generator",
    theme=gr.themes.Soft(primary_hue="blue", secondary_hue="slate"),
    css=".code-output pre { max-height: 600px; overflow-y: auto; }",
) as demo:
    agent_history_state = gr.State([])

    gr.Markdown(DESCRIPTION)

    with gr.Row(equal_height=False):
        # ── Left panel: inputs ───────────────────────────────────────────────
        with gr.Column(scale=1, min_width=340):
            url_input = gr.Textbox(
                label="Target URL",
                placeholder="https://example.com",
                lines=1,
            )
            scenario_input = gr.Textbox(
                label="Test Scenario",
                placeholder=(
                    "Describe what to validate — e.g.:\n"
                    "• Test the login form with valid and invalid credentials\n"
                    "• Verify the checkout flow adds items to the cart\n"
                    "• Check that the search bar returns relevant results"
                ),
                lines=6,
            )
            generate_btn = gr.Button("Generate Script", variant="primary", size="lg")
            clear_btn = gr.Button("Clear", variant="secondary")

            gr.Markdown("### Quick examples")
            gr.Examples(
                examples=EXAMPLE_SCENARIOS,
                inputs=[url_input, scenario_input],
                label="",
            )

            gr.Markdown(
                "---\n"
                "**Requirements:** `ANTHROPIC_API_KEY` in `.env`  \n"
                "**Runtime:** Playwright Chromium (installed automatically)"
            )

        # ── Right panel: output ──────────────────────────────────────────────
        with gr.Column(scale=2):
            chatbot = gr.Chatbot(
                label="Generated Script & Analysis",
                type="messages",
                height=680,
                show_copy_button=True,
                render_markdown=True,
            )

    # ── Wire up events ───────────────────────────────────────────────────────
    gen_outputs = [chatbot, agent_history_state, url_input, scenario_input, generate_btn, generate_btn]

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
        outputs=[chatbot, agent_history_state, url_input, scenario_input],
    )


if __name__ == "__main__":
    demo.launch(server_name="0.0.0.0")
