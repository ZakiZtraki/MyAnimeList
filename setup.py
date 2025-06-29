#!/usr/bin/env python3
"""
Setup script for MAL-Sonarr Sync
"""

import json
import os
import sys

def create_config():
    """Interactive setup to create config.json"""
    print("🚀 MAL-Sonarr Sync Setup")
    print("=" * 50)
    
    config = {
        "sonarr": {},
        "mal": {},
        "sync": {}
    }
    
    # Sonarr configuration
    print("\n📺 Sonarr Configuration")
    print("-" * 25)
    
    sonarr_url = input("Enter your Sonarr URL (e.g., http://localhost:8989): ").strip()
    if not sonarr_url.endswith('/'):
        sonarr_url += '/'
    if not sonarr_url.endswith('api/v3/series'):
        sonarr_url += 'api/v3/series'
    
    config["sonarr"]["api_url"] = sonarr_url
    config["sonarr"]["api_key"] = input("Enter your Sonarr API key: ").strip()
    
    # MAL configuration
    print("\n📋 MyAnimeList Configuration")
    print("-" * 30)
    print("You need to create a MAL API application at:")
    print("https://myanimelist.net/apiconfig")
    print()
    
    config["mal"]["client_id"] = input("Enter your MAL Client ID: ").strip()
    config["mal"]["client_secret"] = input("Enter your MAL Client Secret: ").strip()
    
    redirect_uri = input("Enter redirect URI (default: http://localhost:8765/callback): ").strip()
    if not redirect_uri:
        redirect_uri = "http://localhost:8765/callback"
    config["mal"]["redirect_uri"] = redirect_uri
    
    # Sync configuration
    print("\n⚙️  Sync Configuration")
    print("-" * 20)
    
    default_status = input("Default MAL status (completed/watching/plan_to_watch): ").strip().lower()
    if default_status not in ["completed", "watching", "plan_to_watch", "on_hold", "dropped"]:
        default_status = "completed"
    
    config["sync"]["default_status"] = default_status
    config["sync"]["minimum_match_score"] = 75
    config["sync"]["auto_sync"] = False
    config["sync"]["sync_interval_hours"] = 24
    
    # Save configuration
    try:
        with open("config.json", "w") as f:
            json.dump(config, f, indent=2)
        print(f"\n✅ Configuration saved to config.json")
        return True
    except Exception as e:
        print(f"\n❌ Error saving configuration: {e}")
        return False

def check_dependencies():
    """Check if required packages are installed"""
    required_packages = ["requests", "fuzzywuzzy", "python-levenshtein"]
    missing_packages = []
    
    for package in required_packages:
        try:
            __import__(package.replace("-", "_"))
        except ImportError:
            missing_packages.append(package)
    
    if missing_packages:
        print("❌ Missing required packages:")
        for package in missing_packages:
            print(f"   - {package}")
        print("\nInstall them with:")
        print(f"   pip install {' '.join(missing_packages)}")
        return False
    
    print("✅ All required packages are installed")
    return True

def main():
    print("🔍 Checking dependencies...")
    if not check_dependencies():
        return 1
    
    if os.path.exists("config.json"):
        overwrite = input("\nconfig.json already exists. Overwrite? (y/N): ").lower()
        if not overwrite.startswith('y'):
            print("Setup cancelled.")
            return 0
    
    if create_config():
        print("\n🎉 Setup complete!")
        print("\nNext steps:")
        print("1. Test the connection:")
        print("   python sync_mal_sonarr.py --dry-run")
        print("2. Run your first sync:")
        print("   python sync_mal_sonarr.py")
        return 0
    else:
        print("\n❌ Setup failed!")
        return 1

if __name__ == "__main__":
    sys.exit(main())