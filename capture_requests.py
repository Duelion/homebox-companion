#!/usr/bin/env python3
"""Capture network requests from the ProxmoxVE scripts page."""

import json
from playwright.sync_api import sync_playwright

def main():
    requests_data = []
    responses_with_json = []
    
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context()
        page = context.new_page()
        
        # Capture all network requests
        def handle_request(request):
            requests_data.append({
                "url": request.url,
                "method": request.method,
                "resource_type": request.resource_type
            })
        
        def handle_response(response):
            url = response.url
            # Capture all JSON responses
            if response.status == 200:
                try:
                    content_type = response.headers.get('content-type', '')
                    if 'json' in content_type or 'api/' in url:
                        body = response.text()
                        responses_with_json.append({
                            "url": url,
                            "content_type": content_type,
                            "body": body,
                            "has_metube": 'metube' in body.lower()
                        })
                except Exception as e:
                    print(f"Error reading response from {url}: {e}")
        
        page.on("request", handle_request)
        page.on("response", handle_response)
        
        print("Loading page: https://community-scripts.github.io/ProxmoxVE/scripts")
        page.goto("https://community-scripts.github.io/ProxmoxVE/scripts", wait_until="networkidle")
        
        # Wait a bit more for any lazy-loaded content
        page.wait_for_timeout(5000)
        
        browser.close()
    
    # Print all fetch/xhr requests
    print("\n\nAll fetch/xhr/document requests:")
    print("="*80)
    for req in requests_data:
        if req["resource_type"] in ["fetch", "xhr", "document"]:
            print(f"{req['method']} {req['resource_type']:10} {req['url']}")
    
    # Print JSON responses
    print("\n\nJSON Responses captured:")
    print("="*80)
    for resp in responses_with_json:
        print(f"\nURL: {resp['url']}")
        print(f"Content-Type: {resp['content_type']}")
        print(f"Contains 'metube': {resp['has_metube']}")
        print(f"Body length: {len(resp['body'])} chars")
        
        # If it contains metube, show more details
        if resp['has_metube']:
            print("\n>>> THIS RESPONSE CONTAINS METUBE! <<<")
            # Find and show the metube entry
            try:
                data = json.loads(resp['body'])
                if isinstance(data, list):
                    for item in data:
                        if isinstance(item, dict):
                            # Check if it's a category with scripts
                            if 'scripts' in item:
                                for script in item['scripts']:
                                    if 'metube' in script.get('slug', '').lower() or 'metube' in script.get('name', '').lower():
                                        print(f"\nFound MeTube script:")
                                        print(json.dumps(script, indent=2)[:1000])
                            # Check if it's a script directly
                            elif 'metube' in str(item).lower():
                                print(f"\nFound item with metube:")
                                print(json.dumps(item, indent=2)[:500])
            except json.JSONDecodeError:
                print("Could not parse as JSON")
                # Show raw content around metube
                body = resp['body'].lower()
                idx = body.find('metube')
                if idx != -1:
                    start = max(0, idx - 100)
                    end = min(len(body), idx + 300)
                    print(f"Context around 'metube': ...{resp['body'][start:end]}...")

if __name__ == "__main__":
    main()
