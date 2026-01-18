#!/usr/bin/env python3
"""
Atlas API Discovery Script

Uses Playwright to intercept and analyze network requests on the RBKC Atlas portal
to discover the underlying API structure for planning applications.

Usage:
    python scripts/discover_atlas_api.py
"""

import asyncio
import json
from datetime import datetime
from typing import Dict, Any, List
from playwright.async_api import async_playwright, Request, Response


class AtlasAPIDiscovery:
    """Discover API endpoints used by the Atlas planning portal."""

    def __init__(self):
        self.api_calls: List[Dict[str, Any]] = []
        self.responses: Dict[str, Any] = {}
        self.base_url = "https://atlas.rbkc.gov.uk/"

    async def capture_request(self, request: Request):
        """Capture API requests."""
        url = request.url

        # Filter for interesting requests (API, data, search, planning)
        interesting_patterns = [
            'api', 'search', 'planning', 'application', 'document',
            'query', 'data', 'idox', 'uniform', 'graphql',
            '.json', 'submit', 'results'
        ]

        # Skip static assets
        skip_patterns = [
            '.png', '.jpg', '.jpeg', '.gif', '.svg', '.ico',
            '.css', '.woff', '.woff2', '.ttf', '.eot',
            'fonts.', 'google-analytics', 'gtag', 'analytics',
            'mapbox', '.pbf', 'tiles.', 'sprite'
        ]

        if any(pattern in url.lower() for pattern in skip_patterns):
            return

        if any(pattern in url.lower() for pattern in interesting_patterns):
            call_data = {
                'timestamp': datetime.now().isoformat(),
                'url': url,
                'method': request.method,
                'headers': dict(request.headers),
                'post_data': request.post_data,
                'resource_type': request.resource_type,
            }
            self.api_calls.append(call_data)
            print(f"\n🔍 CAPTURED: {request.method} {url}")

            if request.post_data:
                print(f"   POST Data: {request.post_data[:200]}...")

    async def capture_response(self, response: Response):
        """Capture API responses."""
        url = response.url

        # Filter for interesting responses
        interesting_patterns = [
            'api', 'search', 'planning', 'application', 'document',
            'query', 'data', 'idox', 'uniform', 'graphql',
            '.json', 'submit', 'results'
        ]

        skip_patterns = [
            '.png', '.jpg', '.jpeg', '.gif', '.svg', '.ico',
            '.css', '.woff', '.woff2', '.ttf', '.eot',
            'fonts.', 'google-analytics', 'gtag', 'analytics',
            'mapbox', '.pbf', 'tiles.', 'sprite'
        ]

        if any(pattern in url.lower() for pattern in skip_patterns):
            return

        if any(pattern in url.lower() for pattern in interesting_patterns):
            content_type = response.headers.get('content-type', '')

            if 'json' in content_type or 'application' in content_type:
                try:
                    body = await response.text()
                    self.responses[url] = {
                        'status': response.status,
                        'headers': dict(response.headers),
                        'body_preview': body[:1000] if body else None,
                        'body_length': len(body) if body else 0,
                    }
                    print(f"\n📥 RESPONSE: {response.status} {url}")
                    print(f"   Content-Type: {content_type}")
                    print(f"   Body Preview: {body[:300] if body else 'empty'}...")
                except Exception as e:
                    print(f"   Could not read response body: {e}")

    async def discover(self):
        """Main discovery routine."""
        print("=" * 70)
        print("ATLAS PORTAL API DISCOVERY")
        print("=" * 70)
        print(f"Target: {self.base_url}")
        print("=" * 70)

        async with async_playwright() as p:
            browser = await p.chromium.launch(
                headless=False,  # Show browser for debugging
                slow_mo=500,  # Slow down actions
            )

            context = await browser.new_context(
                viewport={'width': 1920, 'height': 1080},
                user_agent='Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
            )

            page = await context.new_page()

            # Set up request/response interception
            page.on('request', self.capture_request)
            page.on('response', self.capture_response)

            print("\n[1/5] Navigating to Atlas portal...")
            try:
                await page.goto(self.base_url, wait_until='networkidle', timeout=60000)
            except Exception as e:
                print(f"Navigation error: {e}")
                await browser.close()
                return

            await page.wait_for_timeout(3000)

            # Take screenshot
            await page.screenshot(path='atlas_1_homepage.png')
            print("   Screenshot saved: atlas_1_homepage.png")

            # Look for cookie consent / acceptance buttons
            print("\n[2/5] Looking for cookie consent...")
            cookie_buttons = [
                'button:has-text("Accept")',
                'button:has-text("accept all")',
                'button:has-text("Accept all")',
                'button:has-text("I agree")',
                'button:has-text("OK")',
                'button:has-text("Continue")',
                '[class*="cookie"] button',
                '[id*="cookie"] button',
            ]

            for selector in cookie_buttons:
                try:
                    btn = await page.query_selector(selector)
                    if btn:
                        await btn.click()
                        print(f"   Clicked cookie button: {selector}")
                        await page.wait_for_timeout(1000)
                        break
                except Exception:
                    pass

            # Look for navigation to planning/applications
            print("\n[3/5] Looking for planning search functionality...")

            # Try various navigation paths
            nav_selectors = [
                'a:has-text("Planning")',
                'a:has-text("planning")',
                'a:has-text("Applications")',
                'a:has-text("Search")',
                '[href*="planning"]',
                '[href*="application"]',
                '[href*="search"]',
                'nav a',
                'button:has-text("Planning")',
            ]

            for selector in nav_selectors:
                try:
                    elements = await page.query_selector_all(selector)
                    for el in elements[:3]:  # Try first 3 matches
                        text = await el.text_content()
                        href = await el.get_attribute('href')
                        print(f"   Found navigation element: '{text}' -> {href}")
                except Exception:
                    pass

            # Try clicking on planning-related links
            planning_clicked = False
            for selector in ['a:has-text("Planning")', '[href*="planning"]', 'a:has-text("Applications")']:
                try:
                    btn = await page.query_selector(selector)
                    if btn:
                        await btn.click()
                        planning_clicked = True
                        print(f"   Clicked: {selector}")
                        await page.wait_for_timeout(3000)
                        await page.screenshot(path='atlas_2_planning.png')
                        print("   Screenshot saved: atlas_2_planning.png")
                        break
                except Exception as e:
                    print(f"   Could not click {selector}: {e}")

            # Look for search inputs
            print("\n[4/5] Looking for search inputs...")
            search_selectors = [
                'input[type="search"]',
                'input[type="text"]',
                'input[placeholder*="search"]',
                'input[placeholder*="Search"]',
                'input[name*="search"]',
                'input[id*="search"]',
                'input[class*="search"]',
                'input[placeholder*="application"]',
                'input[placeholder*="reference"]',
                'input[placeholder*="address"]',
            ]

            for selector in search_selectors:
                try:
                    inputs = await page.query_selector_all(selector)
                    for inp in inputs[:3]:
                        placeholder = await inp.get_attribute('placeholder')
                        name = await inp.get_attribute('name')
                        inp_id = await inp.get_attribute('id')
                        print(f"   Found input: placeholder='{placeholder}', name='{name}', id='{inp_id}'")
                except Exception:
                    pass

            # Try a sample search
            print("\n[5/5] Attempting sample search...")

            # Try typing in a search box
            search_box = await page.query_selector('input[type="search"], input[type="text"]')
            if search_box:
                try:
                    await search_box.fill("PP/24/")  # RBKC planning reference format
                    await page.keyboard.press('Enter')
                    await page.wait_for_timeout(5000)
                    await page.screenshot(path='atlas_3_search_results.png')
                    print("   Screenshot saved: atlas_3_search_results.png")
                except Exception as e:
                    print(f"   Search error: {e}")

            # Wait a bit more to capture any delayed API calls
            await page.wait_for_timeout(3000)

            # Get page HTML for analysis
            html_content = await page.content()
            with open('atlas_page_content.html', 'w') as f:
                f.write(html_content)
            print("   Page HTML saved: atlas_page_content.html")

            await browser.close()

        # Save results
        self.save_results()

    def save_results(self):
        """Save discovery results to files."""
        print("\n" + "=" * 70)
        print("DISCOVERY RESULTS")
        print("=" * 70)

        # Save API calls
        with open('atlas_api_calls.json', 'w') as f:
            json.dump(self.api_calls, f, indent=2)
        print(f"\n📁 Saved {len(self.api_calls)} API calls to atlas_api_calls.json")

        # Save responses
        with open('atlas_api_responses.json', 'w') as f:
            json.dump(self.responses, f, indent=2)
        print(f"📁 Saved {len(self.responses)} API responses to atlas_api_responses.json")

        # Summary
        print("\n" + "-" * 50)
        print("API ENDPOINTS DISCOVERED:")
        print("-" * 50)

        unique_endpoints = set()
        for call in self.api_calls:
            url = call['url']
            method = call['method']
            unique_endpoints.add(f"{method} {url}")

        for endpoint in sorted(unique_endpoints):
            print(f"  {endpoint}")

        # Highlight key endpoints
        print("\n" + "-" * 50)
        print("KEY ENDPOINTS (potential API):")
        print("-" * 50)

        key_patterns = ['api', 'search', 'application', 'planning', 'document']
        for call in self.api_calls:
            url = call['url']
            if any(p in url.lower() for p in key_patterns):
                print(f"\n  {call['method']} {url}")
                if call.get('post_data'):
                    print(f"  POST data: {call['post_data'][:200]}")

                # Check for interesting headers
                headers = call.get('headers', {})
                auth_headers = {k: v for k, v in headers.items()
                              if any(x in k.lower() for x in ['auth', 'x-', 'token', 'api'])}
                if auth_headers:
                    print(f"  Key headers: {auth_headers}")


async def main():
    discovery = AtlasAPIDiscovery()
    await discovery.discover()


if __name__ == "__main__":
    asyncio.run(main())
