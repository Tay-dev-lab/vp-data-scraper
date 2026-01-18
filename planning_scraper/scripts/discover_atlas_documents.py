#!/usr/bin/env python3
"""
Atlas Documents API Discovery

Specifically targets the documents view to capture document-related API calls.

Usage:
    python scripts/discover_atlas_documents.py
"""

import asyncio
import json
from datetime import datetime
from urllib.parse import unquote, parse_qs, urlparse
from typing import Dict, Any, List
from playwright.async_api import async_playwright, Request, Response


class AtlasDocumentsDiscovery:
    """Discover document API endpoints used by the Atlas planning portal."""

    def __init__(self):
        self.all_requests: List[Dict[str, Any]] = []
        self.all_responses: Dict[str, Any] = {}
        self.base_url = "https://atlas.rbkc.gov.uk/planningsearch/"
        # Use a real application reference from our earlier discovery
        self.test_app_ref = "PP/24/04776"

    async def capture_all_requests(self, request: Request):
        """Capture ALL network requests."""
        url = request.url

        # Skip obvious assets
        skip_patterns = [
            '.png', '.jpg', '.jpeg', '.gif', '.svg', '.ico',
            '.css', '.woff', '.woff2', '.ttf', '.eot',
            'fonts.gstatic', 'fonts.googleapis',
            'sentry.io', 'plausible.io',
        ]

        if any(pattern in url.lower() for pattern in skip_patterns):
            return

        call_data = {
            'timestamp': datetime.now().isoformat(),
            'url': url,
            'method': request.method,
            'resource_type': request.resource_type,
            'headers': dict(request.headers),
            'post_data': request.post_data,
        }
        self.all_requests.append(call_data)

        # Log server functions and document-related requests
        if '_server' in url or 'document' in url.lower() or 'file' in url.lower() or 'pdf' in url.lower():
            print(f"\n🔍 {request.method} {url[:120]}")

    async def capture_all_responses(self, response: Response):
        """Capture ALL responses."""
        url = response.url

        # Skip obvious assets
        skip_patterns = [
            '.png', '.jpg', '.jpeg', '.gif', '.svg', '.ico',
            '.css', '.woff', '.woff2', '.ttf', '.eot',
            'fonts.', 'sentry.io', 'plausible.io',
            'mapbox', '.pbf', 'tiles.', 'sprite'
        ]

        if any(pattern in url.lower() for pattern in skip_patterns):
            return

        content_type = response.headers.get('content-type', '')

        # Capture JSON, JavaScript, and document-related responses
        if any(x in content_type for x in ['json', 'javascript', 'pdf', 'octet-stream']) or \
           any(x in url.lower() for x in ['_server', 'document', 'file', 'download']):
            try:
                body = await response.text()
                self.all_responses[url] = {
                    'status': response.status,
                    'content_type': content_type,
                    'headers': dict(response.headers),
                    'body': body[:10000] if len(body) < 10000 else body[:10000] + '...(truncated)',
                    'body_length': len(body),
                }

                if '_server' in url or 'document' in url.lower():
                    print(f"\n📥 RESPONSE ({response.status}): {url[:80]}")
                    print(f"   Content-Type: {content_type}")
                    print(f"   Body preview: {body[:200]}...")
            except Exception as e:
                pass

    async def discover(self):
        """Main discovery routine."""
        print("=" * 70)
        print("ATLAS DOCUMENTS API DISCOVERY")
        print("=" * 70)
        print(f"Target: {self.base_url}")
        print(f"Test application: {self.test_app_ref}")
        print("=" * 70)

        async with async_playwright() as p:
            browser = await p.chromium.launch(
                headless=False,
                slow_mo=500,
            )

            context = await browser.new_context(
                viewport={'width': 1920, 'height': 1080},
                user_agent='Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
            )

            page = await context.new_page()
            page.on('request', self.capture_all_requests)
            page.on('response', self.capture_all_responses)

            print("\n[1/5] Going directly to application page...")
            app_url = f"{self.base_url}cases/{self.test_app_ref}"
            print(f"   URL: {app_url}")
            await page.goto(app_url, wait_until='networkidle', timeout=60000)
            await page.wait_for_timeout(3000)
            await page.screenshot(path='atlas_docs_1_case.png')
            print("   Screenshot: atlas_docs_1_case.png")

            print("\n[2/5] Looking for Documents tab/section...")
            # Try to find and click documents
            doc_elements = await page.query_selector_all('button, a, [role="tab"], div[class*="tab"]')
            for el in doc_elements:
                try:
                    text = await el.text_content()
                    if text and 'document' in text.lower():
                        print(f"   Found element: '{text}'")
                        await el.click()
                        await page.wait_for_timeout(3000)
                        await page.wait_for_load_state('networkidle')
                        break
                except:
                    pass

            await page.screenshot(path='atlas_docs_2_documents_section.png')
            print("   Screenshot: atlas_docs_2_documents_section.png")

            print("\n[3/5] Looking for document links on page...")
            # Look for any links that might be documents
            all_links = await page.query_selector_all('a')
            doc_links = []
            for link in all_links:
                try:
                    href = await link.get_attribute('href')
                    text = await link.text_content()
                    if href and any(x in (href + str(text)).lower() for x in ['document', 'pdf', 'file', 'download', 'view']):
                        doc_links.append({'href': href, 'text': text})
                        print(f"   Found doc link: '{text}' -> {href}")
                except:
                    pass

            print("\n[4/5] Examining page structure for documents...")
            # Get the page content and look for document-related elements
            page_content = await page.content()

            # Look for mentions of documents or files in the HTML
            import re
            doc_patterns = [
                r'document[s]?[\"\']?\s*:\s*[\[\{]',  # documents: [...] or documents: {...}
                r'file[s]?[\"\']?\s*:\s*[\[\{]',
                r'\.pdf',
                r'download',
                r'uniform',  # Idox Uniform system
                r'idox',
            ]

            for pattern in doc_patterns:
                matches = re.findall(f'.{{50}}{pattern}.{{50}}', page_content, re.IGNORECASE)
                if matches:
                    print(f"\n   Pattern '{pattern}' found:")
                    for match in matches[:3]:
                        print(f"      ...{match}...")

            print("\n[5/5] Looking for iframe or external document sources...")
            iframes = await page.query_selector_all('iframe')
            for iframe in iframes:
                src = await iframe.get_attribute('src')
                print(f"   Found iframe: {src}")

            # Also check for any API calls in window/global scope
            try:
                api_info = await page.evaluate('''() => {
                    const info = {};
                    if (window.$R) info.$R = Object.keys(window.$R);
                    if (window._$HY) info._$HY = typeof window._$HY;
                    if (window.config) info.config = window.config;
                    return info;
                }''')
                print(f"\n   Window globals: {json.dumps(api_info, indent=2)}")
            except:
                pass

            await page.wait_for_timeout(3000)
            await browser.close()

        # Save results
        self.save_results()

    def save_results(self):
        """Save discovery results to files."""
        print("\n" + "=" * 70)
        print("DISCOVERY RESULTS")
        print("=" * 70)

        # Save all requests
        with open('atlas_docs_requests.json', 'w') as f:
            json.dump(self.all_requests, f, indent=2)
        print(f"\n📁 Saved {len(self.all_requests)} requests to atlas_docs_requests.json")

        # Save all responses
        with open('atlas_docs_responses.json', 'w') as f:
            json.dump(self.all_responses, f, indent=2)
        print(f"📁 Saved {len(self.all_responses)} responses to atlas_docs_responses.json")

        # Analyze server functions
        print("\n" + "-" * 50)
        print("ALL SERVER FUNCTION CALLS:")
        print("-" * 50)

        for req in self.all_requests:
            url = req['url']
            if '_server' in url:
                parsed = urlparse(url)
                params = parse_qs(parsed.query)
                func_id = params.get('id', ['unknown'])[0]
                func_name = func_id.split('--')[-1] if '--' in func_id else func_id

                print(f"\n  📦 {func_name}")
                print(f"     Full ID: {func_id}")
                if 'args' in params:
                    args_decoded = unquote(params['args'][0])
                    print(f"     Args: {args_decoded[:150]}...")

        # Check for document-related URLs
        print("\n" + "-" * 50)
        print("DOCUMENT-RELATED URLS:")
        print("-" * 50)

        doc_keywords = ['document', 'file', 'download', 'pdf', 'attachment', 'uniform', 'idox']
        for req in self.all_requests:
            url = req['url'].lower()
            if any(kw in url for kw in doc_keywords):
                print(f"\n  📄 {req['method']} {req['url']}")


async def main():
    discovery = AtlasDocumentsDiscovery()
    await discovery.discover()


if __name__ == "__main__":
    asyncio.run(main())
