"""Capture a real local browser session with bundled example documents.

Run against the temporary memory backend with generation disabled. Requires the
optional `playwright` Python package and a locally installed Chromium browser.
"""

import argparse
from pathlib import Path

import httpx
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    parser = argparse.ArgumentParser(description="Capture the evidence workspace")
    parser.add_argument("--url", default="http://127.0.0.1:8000")
    parser.add_argument("--output", type=Path, default=ROOT / "docs/screenshots/workspace.png")
    options = parser.parse_args()
    base = options.url.rstrip("/")
    with httpx.Client(base_url=base, timeout=30) as client:
        health = client.get("/api/health")
        health.raise_for_status()
        status = health.json()
        if status["backend"] != "memory" or status["generation_enabled"]:
            parser.error("Capture requires temporary memory storage and no answer provider")
        for path in sorted((ROOT / "samples").glob("*.md")):
            payload = {"name": path.name, "content": path.read_text(encoding="utf-8")}
            response = client.post("/api/documents", json=payload)
            if response.status_code == 409:
                existing = client.get("/api/documents").json()["documents"]
                current = next(item for item in existing if item["name"] == path.name)
                response = client.put(f"/api/documents/{current['id']}", json=payload)
            response.raise_for_status()

    options.output.parent.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        try:
            page = browser.new_page(viewport={"width": 1440, "height": 1210})
            page.goto(base + "/", wait_until="networkidle")
            page.locator("#question").fill("What checks must happen before a release can be published?")
            page.locator("#search-button").click()
            page.locator(".source-card").first.wait_for(timeout=30000)
            page.screenshot(path=str(options.output), full_page=True, animations="disabled")
        finally:
            browser.close()
    print(f"Screenshot written to {options.output}")


if __name__ == "__main__":
    main()