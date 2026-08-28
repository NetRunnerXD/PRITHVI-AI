"""Browser harness: focus a district on the dashboard, ask weather, assert locus.

Requires the API on :8000 and the Next app on :3000.

  cd backend
  python scripts/eval_browser.py
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def main() -> int:
    parser = argparse.ArgumentParser(description="Playwright locus check against the live dashboard")
    parser.add_argument("--url", default="http://localhost:3000")
    parser.add_argument("--place", default="Howrah")
    parser.add_argument("--question", default="What's the weather today?")
    parser.add_argument("--forbidden", default="Haldia,Malda")
    parser.add_argument("--width", type=int, default=1280)
    parser.add_argument("--height", type=int, default=900)
    parser.add_argument("--locale", default="en", help="Reply-in locale button: en, hi, bn")
    args = parser.parse_args()
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("Playwright Python not installed. Use the project Playwright MCP:")
        print("  grok mcp list")
        print("  npx -y @playwright/mcp@latest")
        print("Or:  python -m pip install playwright ; python -m playwright install chromium")
        return 2

    forbidden = [p.strip() for p in str(args.forbidden).split(",") if p.strip()]
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": args.width, "height": args.height})
        page.goto(args.url, wait_until="domcontentloaded", timeout=60000)
        search = page.get_by_test_id("district-search")
        search.click()
        search.fill(args.place)
        page.wait_for_timeout(800)
        page.locator("ul.neo button", has_text=args.place).first.click()
        page.get_by_test_id("tab-advisor").click()
        page.get_by_test_id("chat-locus").filter(has_text=args.place).wait_for(timeout=120000)
        if args.locale and args.locale != "en":
            page.get_by_test_id(f"locale-{args.locale}").click()
        box = page.get_by_test_id("chat-input")
        box.wait_for(state="visible")
        box.fill(args.question)
        page.get_by_test_id("chat-send").click()
        page.get_by_test_id("chat-assistant").first.wait_for(timeout=180000)
        page.get_by_test_id("chat-streaming").wait_for(state="detached", timeout=180000)
        locus = page.get_by_test_id("chat-locus").inner_text()
        thread = page.get_by_test_id("chat-thread").inner_text()
        reply = page.get_by_test_id("chat-assistant").last.inner_text()
        browser.close()

    if args.place.lower() not in locus.lower():
        print("FAIL locus chip:", locus)
        return 1
    if args.locale == "en":
        if args.place.lower() not in reply.lower() and args.place.lower() not in thread.lower():
            print("FAIL reply missing place", args.place)
            print(reply[:800])
            return 1
    elif not any(ch.isdigit() for ch in reply):
        print("FAIL Indic reply has no digits")
        print(reply[:800])
        return 1
    if reply.count("—") >= 4 or "⟦" in reply or "⟧" in reply:
        print("FAIL dashed or leaked lock tokens")
        print(reply[:800])
        return 1
    leaked = [n for n in forbidden if n.lower() in reply.lower() and n.lower() not in args.place.lower()]
    if leaked:
        print("FAIL leaked", leaked)
        print(reply[:800])
        return 1
    print("OK", locus)
    print(reply[:400])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
