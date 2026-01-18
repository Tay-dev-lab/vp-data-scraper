#!/usr/bin/env python3
"""
Atlas API Discovery Script v2

More comprehensive API discovery - captures application details and document APIs.

Usage:
    python scripts/discover_atlas_api_v2.py
"""

import asyncio
import json
from datetime import datetime
from urllib.parse import unquote, parse_qs, urlparse
from typing import Dict, Any, List
from playwright.async_api import async_playwright, Request, Response


class AtlasAPIDiscoveryV2:
    """Discover API endpoints used by the Atlas planning portal."""

    def __init__(self):
        self.api_calls: List[Dict[str, Any]] = []
        self.responses: Dict[str, Any] = {}
        self.base_url = "https://atlas.rbkc.gov.uk/planningsearch/"

    async def capture_request(self, request: Request):
        """Capture all XHR/Fetch requests."""
        url = request.url

        # Skip static assets
        skip_patterns = [
            '.png', '.jpg', '.jpeg', '.gif', '.svg', '.ico',
            '.css', '.woff', '.woff2', '.ttf', '.eot',
            'fonts.', 'google-analytics', 'gtag', 'analytics',
            'mapbox', '.pbf', 'tiles.', 'sprite', 'sentry.io',
            'plausible.io'
        ]

        if any(pattern in url.lower() for pattern in skip_patterns):
            return

        # Only capture XHR/Fetch requests (not document loads)
        if request.resource_type in ['fetch', 'xhr']:
            call_data = {
                'timestamp': datetime.now().isoformat(),
                'url': url,
                'method': request.method,
                'headers': dict(request.headers),
                'post_data': request.post_data,
                'resource_type': request.resource_type,
            }
            self.api_calls.append(call_data)

            # Decode the URL if it contains _server endpoint
            if '_server' in url:
                parsed = urlparse(url)
                params = parse_qs(parsed.query)
                func_id = params.get('id', ['unknown'])[0]
                print(f"\n🔍 SERVER FUNCTION: {func_id}")
                print(f"   URL: {url[:120]}...")
                if 'args' in params:
                    try:
                        args_decoded = unquote(params['args'][0])
                        print(f"   Args: {args_decoded[:200]}")
                    except:
                        pass
            else:
                print(f"\n🔍 FETCH: {request.method} {url[:100]}...")

    async def capture_response(self, response: Response):
        """Capture API responses."""
        url = response.url

        # Skip static assets
        skip_patterns = [
            '.png', '.jpg', '.jpeg', '.gif', '.svg', '.ico',
            '.css', '.woff', '.woff2', '.ttf', '.eot',
            'fonts.', 'google-analytics', 'gtag', 'analytics',
            'mapbox', '.pbf', 'tiles.', 'sprite', 'sentry.io',
            'plausible.io', '.js'
        ]

        if any(pattern in url.lower() for pattern in skip_patterns):
            return

        content_type = response.headers.get('content-type', '')

        if 'json' in content_type or '_server' in url:
            try:
                body = await response.text()
                self.responses[url] = {
                    'status': response.status,
                    'headers': dict(response.headers),
                    'body': body if len(body) < 5000 else body[:5000] + '... (truncated)',
                    'body_length': len(body),
                }

                if '_server' in url:
                    print(f"\n📥 RESPONSE ({response.status}): {len(body)} bytes")
                    print(f"   Body preview: {body[:300]}...")
            except Exception as e:
                pass

    async def discover(self):
        """Main discovery routine."""
        print("=" * 70)
        print("ATLAS PORTAL API DISCOVERY v2")
        print("=" * 70)
        print(f"Target: {self.base_url}")
        print("=" * 70)

        async with async_playwright() as p:
            browser = await p.chromium.launch(
                headless=False,
                slow_mo=300,
            )

            context = await browser.new_context(
                viewport={'width': 1920, 'height': 1080},
                user_agent='Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
            )

            page = await context.new_page()
            page.on('request', self.capture_request)
            page.on('response', self.capture_response)

            print("\n[1/6] Navigating to Atlas portal...")
            await page.goto(self.base_url, wait_until='networkidle', timeout=60000)
            await page.wait_for_timeout(2000)

            print("\n[2/6] Searching for an application reference...")
            search_input = await page.query_selector('#searchInput')
            if search_input:
                await search_input.fill("PP/24/")
                await page.wait_for_timeout(2000)  # Wait for autocomplete

                # Take screenshot
                await page.screenshot(path='atlas_v2_1_autocomplete.png')
                print("   Screenshot: atlas_v2_1_autocomplete.png")

            print("\n[3/6] Clicking on first search result...")
            # Look for autocomplete results
            autocomplete_item = await page.query_selector('div:has-text("Case reference:")')
            if autocomplete_item:
                await autocomplete_item.click()
                await page.wait_for_timeout(3000)
                await page.wait_for_load_state('networkidle')
                await page.screenshot(path='atlas_v2_2_application_detail.png')
                print("   Screenshot: atlas_v2_2_application_detail.png")

                # Get current URL
                print(f"   Current URL: {page.url}")

            print("\n[4/6] Looking for documents tab...")
            # Look for Documents tab or link
            doc_selectors = [
                'button:has-text("Documents")',
                'a:has-text("Documents")',
                '[data-tab="documents"]',
                'nav button',
                'div[role="tab"]',
            ]

            for selector in doc_selectors:
                try:
                    elements = await page.query_selector_all(selector)
                    for el in elements[:3]:
                        text = await el.text_content()
                        print(f"   Found tab/button: '{text}'")
                        if 'document' in text.lower():
                            await el.click()
                            await page.wait_for_timeout(2000)
                            await page.screenshot(path='atlas_v2_3_documents.png')
                            print("   Screenshot: atlas_v2_3_documents.png")
                            break
                except Exception:
                    pass

            print("\n[5/6] Testing Advanced Search...")
            # Go back and try advanced search
            await page.goto(self.base_url, wait_until='networkidle', timeout=60000)
            await page.wait_for_timeout(2000)

            # Click Advanced Search
            adv_search = await page.query_selector('button:has-text("Advanced search")')
            if adv_search:
                await adv_search.click()
                await page.wait_for_timeout(2000)
                await page.screenshot(path='atlas_v2_4_advanced_search.png')
                print("   Screenshot: atlas_v2_4_advanced_search.png")

                # Look for date inputs
                date_inputs = await page.query_selector_all('input[type="date"], input[placeholder*="date"], input[name*="date"]')
                print(f"   Found {len(date_inputs)} date inputs")

                # Look for any form fields
                all_inputs = await page.query_selector_all('input, select')
                print(f"   Found {len(all_inputs)} form fields total")

                for inp in all_inputs[:10]:
                    inp_type = await inp.get_attribute('type')
                    inp_name = await inp.get_attribute('name')
                    inp_id = await inp.get_attribute('id')
                    inp_placeholder = await inp.get_attribute('placeholder')
                    print(f"     - type={inp_type}, name={inp_name}, id={inp_id}, placeholder={inp_placeholder}")

            print("\n[6/6] Attempting date-based search...")
            # Try to perform a search with date range
            # Look for search submit button
            search_btns = await page.query_selector_all('button[type="submit"], button:has-text("Search")')
            for btn in search_btns:
                btn_text = await btn.text_content()
                print(f"   Found button: '{btn_text}'")

            await page.wait_for_timeout(3000)
            await browser.close()

        # Save results
        self.save_results()

    def save_results(self):
        """Save discovery results to files."""
        print("\n" + "=" * 70)
        print("DISCOVERY RESULTS")
        print("=" * 70)

        # Save API calls
        with open('atlas_api_calls_v2.json', 'w') as f:
            json.dump(self.api_calls, f, indent=2)
        print(f"\n📁 Saved {len(self.api_calls)} API calls to atlas_api_calls_v2.json")

        # Save responses
        with open('atlas_api_responses_v2.json', 'w') as f:
            json.dump(self.responses, f, indent=2)
        print(f"📁 Saved {len(self.responses)} API responses to atlas_api_responses_v2.json")

        # Analyze server functions
        print("\n" + "-" * 50)
        print("SERVER FUNCTIONS DISCOVERED:")
        print("-" * 50)

        server_functions = {}
        for call in self.api_calls:
            url = call['url']
            if '_server' in url:
                parsed = urlparse(url)
                params = parse_qs(parsed.query)
                func_id = params.get('id', ['unknown'])[0]

                # Clean up the function name
                func_name = func_id.split('--')[-1] if '--' in func_id else func_id

                if func_name not in server_functions:
                    server_functions[func_name] = {
                        'full_id': func_id,
                        'calls': [],
                        'example_args': None
                    }

                if 'args' in params:
                    try:
                        args_decoded = unquote(params['args'][0])
                        server_functions[func_name]['example_args'] = args_decoded
                    except:
                        pass

                server_functions[func_name]['calls'].append(url)

        for func_name, data in server_functions.items():
            print(f"\n  📦 {func_name}")
            print(f"     Full ID: {data['full_id']}")
            print(f"     Call count: {len(data['calls'])}")
            if data['example_args']:
                print(f"     Example args: {data['example_args'][:150]}...")

        # Show response bodies for server functions
        print("\n" + "-" * 50)
        print("SERVER FUNCTION RESPONSES:")
        print("-" * 50)

        for url, resp_data in self.responses.items():
            if '_server' in url:
                parsed = urlparse(url)
                params = parse_qs(parsed.query)
                func_id = params.get('id', ['unknown'])[0]
                func_name = func_id.split('--')[-1] if '--' in func_id else func_id

                print(f"\n  📦 {func_name}")
                print(f"     Status: {resp_data['status']}")
                print(f"     Length: {resp_data['body_length']} bytes")
                body_preview = resp_data.get('body', '')[:500]
                print(f"     Body: {body_preview}")


async def main():
    discovery = AtlasAPIDiscoveryV2()
    await discovery.discover()


if __name__ == "__main__":
    asyncio.run(main())
