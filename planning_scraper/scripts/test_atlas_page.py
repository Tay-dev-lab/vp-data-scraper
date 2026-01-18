#!/usr/bin/env python3
"""
Test script to debug Atlas page content extraction.
"""

import asyncio
import re
from playwright.async_api import async_playwright


async def test_page():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        page = await browser.new_page()

        # Navigate to a case page
        url = "https://atlas.rbkc.gov.uk/planningsearch/cases/PP/25/06735"
        print(f"Navigating to: {url}")

        await page.goto(url, wait_until='domcontentloaded', timeout=60000)
        await page.wait_for_timeout(8000)  # Wait extra time for SPA to render

        # Get page content
        content = await page.content()
        print(f"\nPage content length: {len(content)} bytes")

        # Check for seroval data patterns
        print("\n--- Checking for seroval patterns ---")

        patterns = {
            "caseReference": r'caseReference:"([^"]+)"',
            "address": r'address:"([^"]+)"',
            "applicationStatus": r'applicationStatus:"([^"]+)"',
        }

        for field, pattern in patterns.items():
            match = re.search(pattern, content)
            if match:
                print(f"Found {field}: {match.group(1)[:80]}...")
            else:
                print(f"NOT FOUND: {field}")

        # Try to get $R from window
        print("\n--- Checking window.$R ---")
        js_result = await page.evaluate('''() => {
            if (window.$R) {
                const keys = Object.keys(window.$R);
                const result = {
                    keys: keys,
                    values: {}
                };
                for (const key of keys.slice(0, 3)) {
                    result.values[key] = JSON.stringify(window.$R[key]).slice(0, 500);
                }
                return result;
            }
            return "No $R found";
        }''')
        print(f"$R result: {js_result}")

        # Check for visible text
        print("\n--- Checking visible text ---")
        h1_text = await page.query_selector('h1')
        if h1_text:
            print(f"H1: {await h1_text.text_content()}")

        # Save page content for analysis
        with open('atlas_page_debug.html', 'w') as f:
            f.write(content)
        print("\nSaved page content to atlas_page_debug.html")

        await page.screenshot(path='atlas_page_debug.png')
        print("Saved screenshot to atlas_page_debug.png")

        await browser.close()


if __name__ == "__main__":
    asyncio.run(test_page())
