#!/usr/bin/env python3
"""Show the newest scripts from the API."""

import json
from playwright.sync_api import sync_playwright

def main():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        
        # Directly fetch the categories API
        response = page.request.get("https://community-scripts.github.io/ProxmoxVE/api/categories")
        data = response.json()
        
        browser.close()
    
    # Extract all scripts
    all_scripts = []
    for category in data:
        for script in category.get('scripts', []):
            all_scripts.append({
                'name': script.get('name'),
                'slug': script.get('slug'),
                'date_created': script.get('date_created'),
                'type': script.get('type'),
                'description': script.get('description', '')[:80]
            })
    
    # Remove duplicates by slug
    seen = set()
    unique_scripts = []
    for script in all_scripts:
        if script['slug'] not in seen:
            seen.add(script['slug'])
            unique_scripts.append(script)
    
    # Sort by date_created descending (newest first)
    sorted_scripts = sorted(unique_scripts, key=lambda x: x['date_created'] or '', reverse=True)
    
    print("="*100)
    print("THE REQUEST THAT PROVIDES 'NEWEST SCRIPTS' DATA:")
    print("="*100)
    print("\n  GET https://community-scripts.github.io/ProxmoxVE/api/categories\n")
    print("="*100)
    print("\nTOP 15 NEWEST SCRIPTS (sorted by date_created):")
    print("="*100)
    print(f"{'#':3} {'Date':12} {'Type':6} {'Name':30} {'Slug':25}")
    print("-"*100)
    
    for i, script in enumerate(sorted_scripts[:15], 1):
        print(f"{i:3} {script['date_created']:12} {script['type']:6} {script['name'][:30]:30} {script['slug'][:25]:25}")
    
    print("\n" + "="*100)
    print("The frontend sorts all scripts by 'date_created' field to show 'Newest Scripts'")
    print("="*100)

if __name__ == "__main__":
    main()
