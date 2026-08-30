"""Playwright check of the Models tab for five Indian cities."""

from __future__ import annotations

import json
import sys
from pathlib import Path

from playwright.sync_api import TimeoutError as PwTimeout
from playwright.sync_api import sync_playwright

CITIES = ["Haldia", "Jaipur", "Pune", "Chennai", "Guwahati"]
OUT = Path(__file__).resolve().parents[2] / ".cache" / "browser_verify"
URL = "http://127.0.0.1:3000"


def pick_city(page, name: str) -> None:
    box = page.locator('input[placeholder*="Search"]')
    box.click()
    box.fill("")
    box.fill(name)
    page.wait_for_timeout(900)
    page.locator("ul.neo li button").first.wait_for(state="visible", timeout=20000)
    exact = page.locator("ul.neo li button").filter(has_text=f"{name},")
    if exact.count():
        exact.first.click()
    else:
        page.locator("ul.neo li button").first.click()


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    results = []
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1400, "height": 900})
        page.goto(URL, wait_until="domcontentloaded", timeout=120000)
        page.locator("nav").get_by_text("Models", exact=True).wait_for(timeout=60000)
        for city in CITIES:
            rec = {"city": city, "ok": False, "errors": []}
            try:
                if city != "Haldia":
                    pick_city(page, city)
                    page.keyboard.press("Escape")
                page.locator("aside p.truncate").filter(has_text=city).wait_for(timeout=120000)
                page.locator("nav").get_by_text("Models", exact=True).click()
                page.get_by_text("VERA-MoE architecture").wait_for(timeout=30000)
                body = page.inner_text("body")
                rec["has_vera"] = "VERA-MoE" in body
                rec["has_gate"] = "Adaptive" in body and "gate" in body.lower()
                rec["has_sat"] = "Satellite" in body or "INSAT" in body or "computer vision" in body.lower()
                rec["has_pdf"] = "Mixture" in body
                rec["has_hourly"] = "0–48" in body or "0-48" in body or "48 H" in body.upper()
                rec["has_mlops"] = "MLOps" in body
                rec["pin"] = city.lower() in body.lower()
                rec["rain3"] = page.locator("body").inner_text()
                missing = [k for k in ("has_vera", "has_gate", "has_sat", "has_hourly", "has_mlops", "pin") if not rec[k]]
                rec["ok"] = rec["has_vera"] and rec["pin"] and not missing
                rec.pop("rain3", None)
                rec["missing"] = missing
                shot = OUT / f"{city.lower()}.png"
                page.screenshot(path=str(shot), full_page=True)
                rec["screenshot"] = str(shot)
            except PwTimeout as e:
                rec["errors"].append(f"timeout: {e}")
                page.screenshot(path=str(OUT / f"{city.lower()}_fail.png"), full_page=True)
            except Exception as e:
                rec["errors"].append(str(e)[:400])
                page.screenshot(path=str(OUT / f"{city.lower()}_fail.png"), full_page=True)
            results.append(rec)
        browser.close()
    (OUT / "report.json").write_text(json.dumps(results, indent=2), encoding="utf-8")
    print(json.dumps(results, indent=2))
    return 0 if all(r["ok"] for r in results) else 1


if __name__ == "__main__":
    sys.exit(main())
