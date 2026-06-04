"""Playwright-based tools for page navigation and element extraction."""

import base64
import json
from playwright.sync_api import sync_playwright


def navigate_and_capture(url: str) -> dict:
    """Navigate to a URL, take a screenshot, and return page metadata."""
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1280, "height": 720})
        try:
            page.goto(url, timeout=30000, wait_until="domcontentloaded")
            page.wait_for_load_state("networkidle", timeout=10000)
        except Exception:
            pass  # proceed even if networkidle times out

        title = page.title()
        current_url = page.url
        screenshot_bytes = page.screenshot(full_page=False)
        screenshot_b64 = base64.b64encode(screenshot_bytes).decode()

        # Lightweight HTML snippet for structure context (avoid sending full DOM)
        html_snippet = page.content()[:6000]
        browser.close()

    return {
        "title": title,
        "url": current_url,
        "screenshot_base64": screenshot_b64,
        "html_snippet": html_snippet,
    }


def extract_page_elements(url: str) -> dict:
    """Extract all interactive elements from a page with XPaths and CSS selectors."""
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1280, "height": 720})
        try:
            page.goto(url, timeout=30000, wait_until="domcontentloaded")
            page.wait_for_load_state("networkidle", timeout=10000)
        except Exception:
            pass

        elements = page.evaluate("""() => {
            function getXPath(el) {
                if (el.id) return '//*[@id="' + el.id + '"]';
                const parts = [];
                let node = el;
                while (node && node.nodeType === Node.ELEMENT_NODE) {
                    let idx = 0;
                    let sib = node.previousSibling;
                    while (sib) {
                        if (sib.nodeType === Node.ELEMENT_NODE && sib.tagName === node.tagName) idx++;
                        sib = sib.previousSibling;
                    }
                    const tag = node.tagName.toLowerCase();
                    parts.unshift(idx > 0 ? tag + '[' + (idx + 1) + ']' : tag);
                    node = node.parentElement;
                }
                return '/' + parts.join('/');
            }

            function getCssSelector(el) {
                if (el.id) return '#' + CSS.escape(el.id);
                if (el.getAttribute('data-testid')) return `[data-testid="${el.getAttribute('data-testid')}"]`;
                if (el.name) return `${el.tagName.toLowerCase()}[name="${el.name}"]`;
                if (el.getAttribute('aria-label')) return `[aria-label="${el.getAttribute('aria-label')}"]`;
                return el.tagName.toLowerCase();
            }

            const targets = ['input', 'button', 'select', 'textarea',
                             'a[href]', 'form', '[role="button"]',
                             '[role="link"]', '[role="checkbox"]', '[role="radio"]',
                             '[role="textbox"]', '[role="combobox"]'];
            const seen = new Set();
            const result = [];

            targets.forEach(sel => {
                document.querySelectorAll(sel).forEach(el => {
                    const rect = el.getBoundingClientRect();
                    if (rect.width === 0 && rect.height === 0) return;
                    const xpath = getXPath(el);
                    if (seen.has(xpath)) return;
                    seen.add(xpath);

                    const innerText = (el.innerText || '').trim().substring(0, 120);
                    const value = (el.value || '').trim().substring(0, 80);

                    result.push({
                        tag: el.tagName.toLowerCase(),
                        id: el.id || null,
                        name: el.getAttribute('name') || null,
                        type: el.getAttribute('type') || null,
                        placeholder: el.getAttribute('placeholder') || null,
                        aria_label: el.getAttribute('aria-label') || null,
                        data_testid: el.getAttribute('data-testid') || null,
                        role: el.getAttribute('role') || null,
                        text: innerText || value || null,
                        href: el.getAttribute('href') || null,
                        css_selector: getCssSelector(el),
                        xpath: xpath,
                        class_names: el.className || null,
                    });
                });
            });

            return result.slice(0, 60);
        }""")

        page_title = page.title()
        page_url = page.url
        browser.close()

    return {
        "page_title": page_title,
        "page_url": page_url,
        "element_count": len(elements),
        "elements": elements,
    }
