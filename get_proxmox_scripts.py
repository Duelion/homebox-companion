#!/usr/bin/env python3
"""
Fetch and parse Proxmox VE Helper Scripts from the community-scripts API.
Returns a list of scripts sorted by date_created (newest first).
"""

import json
import urllib.request
from typing import Any


def fetch_scripts() -> list[dict[str, Any]]:
    """
    Fetch all scripts from the Proxmox VE Helper Scripts API.
    
    Returns:
        List of script dictionaries sorted by date_created (newest first).
    """
    url = "https://community-scripts.github.io/ProxmoxVE/api/categories"
    
    # Fetch the data
    with urllib.request.urlopen(url) as response:
        data = json.loads(response.read().decode('utf-8'))
    
    # Extract all scripts from all categories
    all_scripts = []
    seen_slugs = set()
    
    for category in data:
        category_name = category.get('name', 'Unknown')
        category_id = category.get('id')
        
        for script in category.get('scripts', []):
            slug = script.get('slug')
            
            # Skip duplicates (same script can appear in multiple categories)
            if slug in seen_slugs:
                continue
            seen_slugs.add(slug)
            
            # Extract available information
            script_info = {
                'name': script.get('name'),
                'slug': slug,
                'type': script.get('type'),  # ct, vm, pve, addon
                'date_created': script.get('date_created'),
                'description': script.get('description'),
                'logo': script.get('logo'),
                'website': script.get('website'),
                'documentation': script.get('documentation'),
                'interface_port': script.get('interface_port'),
                'updateable': script.get('updateable'),
                'privileged': script.get('privileged'),
                'config_path': script.get('config_path'),
                'categories': script.get('categories', []),
                'default_credentials': script.get('default_credentials'),
                'install_methods': script.get('install_methods', []),
                'notes': script.get('notes', []),
            }
            
            # Extract resource requirements from install_methods
            if script_info['install_methods']:
                default_method = script_info['install_methods'][0]
                resources = default_method.get('resources', {})
                script_info['resources'] = {
                    'cpu': resources.get('cpu'),
                    'ram': resources.get('ram'),  # in MB
                    'hdd': resources.get('hdd'),  # in GB
                    'os': resources.get('os'),
                    'version': resources.get('version'),
                }
            else:
                script_info['resources'] = None
            
            all_scripts.append(script_info)
    
    # Sort by date_created (newest first)
    all_scripts.sort(key=lambda x: x['date_created'] or '', reverse=True)
    
    return all_scripts


def print_scripts_table(scripts: list[dict], limit: int = 20) -> None:
    """Print scripts in a formatted table."""
    print(f"\n{'='*120}")
    print(f"PROXMOX VE HELPER SCRIPTS - Sorted by Date (Newest First)")
    print(f"{'='*120}")
    print(f"{'#':>3} {'Date':12} {'Type':6} {'Name':30} {'Port':>6} {'Resources':20} {'Slug'}")
    print(f"{'-'*120}")
    
    for i, script in enumerate(scripts[:limit], 1):
        resources = script.get('resources')
        if resources and resources.get('cpu'):
            res_str = f"{resources['cpu']}C/{resources['ram']}MB/{resources['hdd']}GB"
        else:
            res_str = "N/A"
        
        port = script.get('interface_port') or ''
        print(f"{i:>3} {script['date_created']:12} {script['type']:6} {script['name'][:30]:30} {str(port):>6} {res_str:20} {script['slug']}")
    
    print(f"\nTotal scripts: {len(scripts)}")


def main():
    """Main function to fetch and display scripts."""
    print("Fetching scripts from community-scripts.github.io...")
    scripts = fetch_scripts()
    
    # Print table of newest scripts
    print_scripts_table(scripts, limit=25)
    
    # Print full details of the newest script
    print(f"\n{'='*120}")
    print("NEWEST SCRIPT DETAILS:")
    print(f"{'='*120}")
    if scripts:
        newest = scripts[0]
        for key, value in newest.items():
            if value is not None and value != [] and value != {}:
                if isinstance(value, (dict, list)):
                    print(f"{key}: {json.dumps(value, indent=2)}")
                else:
                    print(f"{key}: {value}")
    
    # Save to JSON file
    output_file = "/workspace/proxmox_scripts.json"
    with open(output_file, 'w') as f:
        json.dump(scripts, f, indent=2)
    print(f"\n\nFull data saved to: {output_file}")
    
    return scripts


if __name__ == "__main__":
    scripts = main()
