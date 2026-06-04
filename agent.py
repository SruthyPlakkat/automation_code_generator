"""Core agent logic — Claude tool-use loop for automation script generation."""

from __future__ import annotations

import json
import os
from dotenv import load_dotenv
import anthropic

from tools import navigate_and_capture, extract_page_elements

load_dotenv(override=True)

MODEL = "claude-sonnet-4-6"

TOOLS: list[dict] = [
    {
        "name": "navigate_and_capture",
        "description": (
            "Open a URL in a headless Chromium browser, take a full-viewport screenshot, "
            "and return the page title, resolved URL, and an HTML snippet. "
            "Always call this first to understand the visual layout of the page."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "url": {"type": "string", "description": "Fully-qualified URL to navigate to."}
            },
            "required": ["url"],
        },
    },
    {
        "name": "extract_page_elements",
        "description": (
            "Scan the page at the given URL and return a structured list of every interactive "
            "element (inputs, buttons, links, selects, textareas, ARIA roles) together with "
            "its XPath, CSS selector, id, name, placeholder, aria-label, data-testid, and "
            "visible text. Use this to discover selectors for the test script."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "url": {"type": "string", "description": "Fully-qualified URL to extract elements from."}
            },
            "required": ["url"],
        },
    },
]

SYSTEM_PROMPT = """\
You are a senior test automation engineer specialising in Playwright (Python).

## Your workflow
1. Receive a URL and a user-described test scenario.
2. Call `navigate_and_capture` to understand the page layout (title, URL, HTML structure).
3. Call `extract_page_elements` to discover every interactive element and its best selector.
4. Map the user scenario to the identified elements.
5. Produce a complete, runnable Playwright pytest script.

## Script requirements
- Imports: `import re`, `from playwright.sync_api import Page, expect`
- Use `pytest-playwright` page fixture.
- Selector priority: `data-testid` > `id` (#id) > `name` attr > `aria-label` > visible text > CSS > XPath (last resort).
- Every interaction must have at least one `expect(...)` assertion.
- Use `page.wait_for_load_state("networkidle")` after navigations.
- Add a one-line comment before each logical test step.
- No skeleton / placeholder code — write real, executable tests.
- Wrap tests in a pytest class named `Test<PageName>`.

## Output format (strict)
After collecting page data, reply with:
1. **Page Summary** — 2-3 sentences on what the page does and which elements map to the scenario.
2. **Generated Test Script** — inside a ```python ... ``` code block.
3. **Run instructions** — short commands to install deps and execute tests.
"""


def _call_tool(name: str, inputs: dict) -> str:
    if name == "navigate_and_capture":
        result = navigate_and_capture(inputs["url"])
        # Omit screenshot bytes from the tool-result text (Claude doesn't need raw base64 here)
        return json.dumps({
            "title": result["title"],
            "url": result["url"],
            "html_snippet": result["html_snippet"],
        })
    if name == "extract_page_elements":
        result = extract_page_elements(inputs["url"])
        return json.dumps(result)
    return json.dumps({"error": f"Unknown tool: {name}"})


def run_agent(
    url: str,
    scenario: str,
    conversation_history: list[dict],
    status_callback=None,
) -> tuple[list[dict], str]:
    """
    Drive the Claude tool-use loop and return (updated_history, final_text).

    status_callback(msg: str) is called with progress updates so the UI can
    stream partial state to the user.
    """
    client = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))

    user_content = f"**URL:** {url}\n\n**Test Scenario:**\n{scenario}"
    messages: list[dict] = list(conversation_history) + [
        {"role": "user", "content": user_content}
    ]

    while True:
        response = client.messages.create(
            model=MODEL,
            max_tokens=8096,
            system=SYSTEM_PROMPT,
            tools=TOOLS,
            messages=messages,
            betas=["prompt-caching-2024-07-31"],  # cache system prompt across turns
        )

        messages.append({"role": "assistant", "content": response.content})

        if response.stop_reason == "end_turn":
            text = _extract_text(response.content)
            return messages, text

        if response.stop_reason == "tool_use":
            tool_results = []
            for block in response.content:
                if block.type == "tool_use":
                    if status_callback:
                        status_callback(f"Calling tool: `{block.name}({block.input})`...")
                    result_json = _call_tool(block.name, block.input)
                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": result_json,
                    })
            messages.append({"role": "user", "content": tool_results})
        else:
            # Unexpected stop reason — surface whatever text exists
            break

    return messages, _extract_text(response.content)


def _extract_text(content) -> str:
    return next(
        (block.text for block in content if hasattr(block, "text") and block.text),
        "No response generated.",
    )
