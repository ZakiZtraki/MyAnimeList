import requests
import json
import base64
import hashlib
import os
import secrets
import time
import re
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
import webbrowser
from fuzzywuzzy import fuzz, process
from datetime import datetime, timedelta

# Configuration Management
CONFIG_FILE = "config.json"
TOKEN_FILE = "mal_token.json"

def load_config():
    """Load configuration from file or use defaults."""
    default_config = {
        "sonarr": {
            "api_url": "http://localhost:8989/api/v3/series",
            "api_key": ""
        },
        "mal": {
            "client_id": "",
            "client_secret": "",
            "redirect_uri": "http://localhost:8765/callback"
        },
        "sync": {
            "default_status": "completed",
            "minimum_match_score": 75,
            "auto_sync": False,
            "sync_interval_hours": 24
        }
    }
    
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r") as f:
                user_config = json.load(f)
            # Merge with defaults
            for section in default_config:
                if section in user_config:
                    default_config[section].update(user_config[section])
            return default_config
        except Exception as e:
            print(f"Error loading config file: {e}")
            print("Using default configuration...")
    
    return default_config

# Load configuration
config = load_config()

# Extract configuration values for backward compatibility
SONARR_API_URL = config["sonarr"]["api_url"]
SONARR_API_KEY = config["sonarr"]["api_key"]
MAL_CLIENT_ID = config["mal"]["client_id"]
MAL_CLIENT_SECRET = config["mal"]["client_secret"]
MAL_REDIRECT_URI = config["mal"]["redirect_uri"]

def save_token(token):
    # Add expiration time
    if 'expires_in' in token:
        expires_at = datetime.now() + timedelta(seconds=token['expires_in'])
        token['expires_at'] = expires_at.isoformat()
    
    with open(TOKEN_FILE, "w") as f:
        json.dump(token, f)

def load_token():
    if os.path.exists(TOKEN_FILE):
        with open(TOKEN_FILE, "r") as f:
            token_data = json.load(f)
            # Check if token is expired
            if 'expires_at' in token_data:
                if datetime.now() >= datetime.fromisoformat(token_data['expires_at']):
                    print("Token expired, will need to refresh...")
                    return None
            return token_data
    return None

def refresh_token(refresh_token):
    token_url = "https://myanimelist.net/v1/oauth2/token"
    data = {
        "client_id": MAL_CLIENT_ID,
        "client_secret": MAL_CLIENT_SECRET,
        "grant_type": "refresh_token",
        "refresh_token": refresh_token,
    }
    response = requests.post(token_url, data=data)
    response.raise_for_status()
    token = response.json()
    save_token(token)
    return token["access_token"], token["refresh_token"]

class OAuthHandler(BaseHTTPRequestHandler):
    code = None
    def do_GET(self):
        parsed = urlparse(self.path)
        params = parse_qs(parsed.query)
        if "code" in params:
            OAuthHandler.code = params["code"][0]
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"You can close this window and return to the script.")
        else:
            self.send_response(400)
            self.end_headers()
            self.wfile.write(b"No code found.")

# Step 1: Authenticate with MyAnimeList (OAuth2)
def get_mal_access_token():
    token = load_token()
    if token:
        # Check if token needs refreshing
        if 'expires_at' in token:
            if datetime.now() >= datetime.fromisoformat(token['expires_at']) - timedelta(minutes=5):
                # Token will expire in 5 minutes or less, refresh it
                if 'refresh_token' in token:
                    try:
                        print("Refreshing access token...")
                        new_access_token, new_refresh_token = refresh_token(token['refresh_token'])
                        return new_access_token
                    except Exception as e:
                        print(f"Token refresh failed: {e}")
                        print("Need to re-authenticate...")
                else:
                    print("No refresh token available, need to re-authenticate...")
            else:
                return token["access_token"]

    # Generate a secure code_verifier for PKCE (MAL uses "plain" method)
    code_verifier = base64.urlsafe_b64encode(secrets.token_bytes(32)).rstrip(b'=').decode('utf-8')
    
    # CRITICAL FIX: For MAL API, use "plain" method (code_challenge = code_verifier)
    # MAL does NOT support S256, only "plain"
    code_challenge = code_verifier
    
    # Generate state for security
    state = base64.urlsafe_b64encode(secrets.token_bytes(16)).rstrip(b'=').decode('utf-8')
    
    auth_url = (
        f"https://myanimelist.net/v1/oauth2/authorize?response_type=code"
        f"&client_id={MAL_CLIENT_ID}&redirect_uri={MAL_REDIRECT_URI}"
        f"&code_challenge={code_challenge}&code_challenge_method=plain"
        f"&state={state}"
    )
    print(f"Opening browser for authorization...")
    print(f"URL: {auth_url}")
    webbrowser.open(auth_url)

    # Reset handler state
    OAuthHandler.code = None

    # Start local server to catch the redirect
    server = HTTPServer(("localhost", 8765), OAuthHandler)
    print("Waiting for authorization callback...")
    print("Please complete the authorization in your browser...")
    
    # Handle multiple requests if needed with timeout
    timeout_count = 0
    max_timeout = 30  # 30 seconds timeout
    
    while OAuthHandler.code is None and timeout_count < max_timeout:
        server.timeout = 1
        server.handle_request()
        timeout_count += 1
        if timeout_count % 10 == 0:
            print(f"Still waiting for authorization... ({timeout_count}s)")
    
    if OAuthHandler.code is None:
        raise Exception("Authorization timeout - no code received")
    
    code = OAuthHandler.code
    print("✅ Authorization code received!")

    token_url = "https://myanimelist.net/v1/oauth2/token"
    data = {
        "client_id": MAL_CLIENT_ID,
        "client_secret": MAL_CLIENT_SECRET,
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": MAL_REDIRECT_URI,
        "code_verifier": code_verifier
    }
    response = requests.post(token_url, data=data)
    response.raise_for_status()
    token = response.json()
    save_token(token)
    return token["access_token"]

# Step 2: Fetch anime from Sonarr
def get_sonarr_tags():
    """Fetch all tags from Sonarr to resolve tag IDs to names."""
    headers = {"X-Api-Key": SONARR_API_KEY}
    tag_url = SONARR_API_URL.replace('/series', '/tag')
    try:
        response = requests.get(tag_url, headers=headers)
        response.raise_for_status()
        tags = response.json()
        return {tag['id']: tag['label'].lower() for tag in tags}
    except Exception as e:
        print(f"Warning: Could not fetch tags from Sonarr: {e}")
        return {}

def get_sonarr_anime():
    headers = {"X-Api-Key": SONARR_API_KEY}
    response = requests.get(SONARR_API_URL, headers=headers)
    response.raise_for_status()
    all_series = response.json()
    
    # Get tag mappings
    tag_mapping = get_sonarr_tags()
    
    # Filter series with tag 'anime' (case-insensitive)
    anime_series = []
    for series in all_series:
        is_anime = False
        
        # Check tags
        tags = series.get('tags', [])
        for tag_id in tags:
            tag_name = tag_mapping.get(tag_id, str(tag_id))
            if 'anime' in tag_name.lower():
                is_anime = True
                break
        
        # Also check if the series type is anime or title contains anime keywords
        series_type = series.get('seriesType', '').lower()
        title = series.get('title', '').lower()
        
        if not is_anime:
            # Check series type
            if series_type == 'anime':
                is_anime = True
            # Check title for anime indicators
            elif any(keyword in title for keyword in ['anime', '(tv)', 'season', 'cour']):
                is_anime = True
        
        if is_anime:
            anime_series.append(series)
    
    return anime_series

# Improved anime title cleaning for better matching
def clean_anime_title(title):
    """Clean anime title for better matching."""
    # Remove common suffixes and patterns
    title = re.sub(r'\s*\(\d{4}\)$', '', title)  # Remove year in parentheses
    title = re.sub(r'\s*Season\s+\d+', '', title, flags=re.IGNORECASE)  # Remove "Season X"
    title = re.sub(r'\s*S\d+$', '', title)  # Remove "S1", "S2", etc.
    title = re.sub(r'\s*\d+(?:st|nd|rd|th)\s+Season', '', title, flags=re.IGNORECASE)
    title = re.sub(r'\s*Part\s+\d+', '', title, flags=re.IGNORECASE)  # Remove "Part X"
    title = re.sub(r'\s*Cour\s+\d+', '', title, flags=re.IGNORECASE)  # Remove "Cour X"
    title = re.sub(r'\s*\[.*?\]', '', title)  # Remove content in square brackets
    title = re.sub(r'\s*\(.*?\)', '', title)  # Remove content in parentheses
    title = re.sub(r'\s+', ' ', title).strip()  # Normalize whitespace
    return title

# Search for anime on MyAnimeList by title
def search_mal_anime(title, access_token, max_results=10):
    """Search MAL for an anime by title and return the best match using fuzzy matching."""
    # Clean the title
    cleaned_title = clean_anime_title(title)
    
    url = "https://api.myanimelist.net/v2/anime"
    headers = {"Authorization": f"Bearer {access_token}"}
    params = {
        "q": cleaned_title,
        "limit": max_results,
        "fields": "id,title,alternative_titles,start_date,media_type"
    }
    
    try:
        resp = requests.get(url, headers=headers, params=params)
        resp.raise_for_status()
        
        if not resp.json().get('data'):
            # Try with original title if cleaned title doesn't work
            params["q"] = title
            resp = requests.get(url, headers=headers, params=params)
            resp.raise_for_status()
            
            if not resp.json().get('data'):
                return None, None, None, 0
        
        results = resp.json()['data']
        best_match = None
        best_score = 0
        
        for result in results:
            anime = result['node']
            
            # Get all possible titles for this anime
            titles_to_check = [anime['title']]
            
            # Add alternative titles
            alt_titles = anime.get('alternative_titles', {})
            if alt_titles.get('en'):
                titles_to_check.append(alt_titles['en'])
            if alt_titles.get('ja'):
                titles_to_check.append(alt_titles['ja'])
            if alt_titles.get('synonyms'):
                titles_to_check.extend(alt_titles['synonyms'])
            
            # Calculate fuzzy match scores
            for check_title in titles_to_check:
                # Clean the MAL title too
                cleaned_check_title = clean_anime_title(check_title)
                
                # Multiple scoring methods
                ratio_score = fuzz.ratio(cleaned_title.lower(), cleaned_check_title.lower())
                partial_score = fuzz.partial_ratio(cleaned_title.lower(), cleaned_check_title.lower())
                token_score = fuzz.token_sort_ratio(cleaned_title.lower(), cleaned_check_title.lower())
                
                # Weighted average (token sort is usually best for anime titles)
                combined_score = (ratio_score * 0.3 + partial_score * 0.3 + token_score * 0.4)
                
                if combined_score > best_score:
                    best_score = combined_score
                    best_match = anime
        
        min_score = config.get("sync", {}).get("minimum_match_score", 75)
        if best_match and best_score >= min_score:
            return (
                best_match['id'],
                best_match['title'],
                best_match.get('start_date'),
                best_score
            )
    
    except Exception as e:
        print(f"Error searching MAL for '{title}': {e}")
    
    return None, None, None, 0

# Check if anime is already in user's MAL list
def get_mal_list_status(anime_id, access_token):
    """Get current status of anime in user's MAL list."""
    url = f"https://api.myanimelist.net/v2/anime/{anime_id}"
    headers = {"Authorization": f"Bearer {access_token}"}
    params = {"fields": "my_list_status"}
    
    try:
        resp = requests.get(url, headers=headers, params=params)
        resp.raise_for_status()
        data = resp.json()
        return data.get('my_list_status')
    except Exception:
        return None

# Update the user's MyAnimeList
def update_mal_list(anime_id, access_token, status="completed", score=None):
    """Add or update an anime in the user's MAL list."""
    url = f"https://api.myanimelist.net/v2/anime/{anime_id}/my_list_status"
    headers = {"Authorization": f"Bearer {access_token}"}
    data = {"status": status}
    
    if score is not None:
        data["score"] = score
    
    try:
        # Add rate limiting
        time.sleep(1)  # Be nice to the API
        resp = requests.put(url, headers=headers, data=data)
        resp.raise_for_status()
        return True, resp.json()
    except requests.exceptions.HTTPError as e:
        if e.response.status_code == 429:  # Rate limited
            print("Rate limited, waiting...")
            time.sleep(5)
            return False, f"Rate limited: {e}"
        return False, f"HTTP Error: {e}"
    except Exception as e:
        return False, f"Error: {e}"

# Step 3: Sync with MyAnimeList
def sync_with_mal(anime_list, access_token, interactive=True, default_status="completed"):
    """Sync Sonarr anime with MyAnimeList."""
    print(f"Found {len(anime_list)} anime series in Sonarr")
    print("=" * 60)
    
    updated_count = 0
    skipped_count = 0
    failed_count = 0
    
    for i, anime in enumerate(anime_list, 1):
        title = anime.get('title')
        sonarr_status = anime.get('status', 'Unknown')
        
        print(f"\n[{i}/{len(anime_list)}] Processing: {title}")
        print(f"Sonarr Status: {sonarr_status}")
        
        # Search for anime on MAL
        mal_id, mal_title, mal_year, match_score = search_mal_anime(title, access_token)
        
        if not mal_id:
            print(f"❌ No MAL match found for: {title}")
            failed_count += 1
            continue
            
        print(f"✅ Found MAL match: {mal_title}")
        print(f"   MAL ID: {mal_id}")
        print(f"   Year: {mal_year}")
        print(f"   Match Score: {match_score:.1f}%")
        
        # Check if already in MAL list
        current_status = get_mal_list_status(mal_id, access_token)
        if current_status:
            print(f"   Already in MAL list with status: {current_status.get('status', 'unknown')}")
            if interactive:
                update_anyway = input("   Update anyway? (y/N): ").lower().startswith('y')
                if not update_anyway:
                    print("   Skipping...")
                    skipped_count += 1
                    continue
        
        # Determine status based on Sonarr status
        if sonarr_status.lower() == 'continuing':
            mal_status = "watching"
        elif sonarr_status.lower() in ['ended', 'completed']:
            mal_status = default_status
        else:
            mal_status = default_status
        
        if interactive and match_score < 90:
            print(f"   Low match score ({match_score:.1f}%). Confirm update?")
            confirm = input(f"   Add '{mal_title}' to MAL as '{mal_status}'? (y/N): ").lower()
            if not confirm.startswith('y'):
                print("   Skipping...")
                skipped_count += 1
                continue
        
        # Update MAL list
        print(f"   Updating MAL list with status: {mal_status}")
        success, result = update_mal_list(mal_id, access_token, status=mal_status)
        
        if success:
            print(f"   ✅ Successfully updated {mal_title} in your MAL list.")
            updated_count += 1
        else:
            print(f"   ❌ Failed to update {mal_title}: {result}")
            failed_count += 1
        
        # Small delay to be nice to the API
        time.sleep(1)
    
    print("\n" + "=" * 60)
    print("SYNC COMPLETE")
    print(f"Updated: {updated_count}")
    print(f"Skipped: {skipped_count}")
    print(f"Failed: {failed_count}")
    print(f"Total processed: {len(anime_list)}")
    print("=" * 60)

def main():
    import argparse
    
    parser = argparse.ArgumentParser(description="Sync Sonarr anime with MyAnimeList")
    parser.add_argument("--non-interactive", action="store_true", 
                       help="Run without user prompts")
    parser.add_argument("--status", default="completed", 
                       choices=["watching", "completed", "on_hold", "dropped", "plan_to_watch"],
                       help="Default MAL status for synced anime")
    parser.add_argument("--dry-run", action="store_true",
                       help="Show what would be synced without making changes")
    
    args = parser.parse_args()
    
    try:
        print("🚀 Starting MAL-Sonarr Sync...")
        print("=" * 60)
        
        # Get access token
        print("🔐 Authenticating with MyAnimeList...")
        access_token = get_mal_access_token()
        if not access_token:
            print("❌ Failed to get MAL access token")
            return
        print("✅ Authentication successful")
        
        # Get anime from Sonarr
        print("📺 Fetching anime from Sonarr...")
        anime_list = get_sonarr_anime()
        if not anime_list:
            print("❌ No anime found in Sonarr or failed to fetch")
            return
        print(f"✅ Found {len(anime_list)} anime series")
        
        if args.dry_run:
            print("\n🔍 DRY RUN - No changes will be made")
            print("=" * 60)
            for i, anime in enumerate(anime_list, 1):
                title = anime.get('title')
                status = anime.get('status', 'Unknown')
                print(f"{i:3}. {title} (Status: {status})")
            return
        
        # Sync with MAL
        sync_with_mal(
            anime_list, 
            access_token, 
            interactive=not args.non_interactive,
            default_status=args.status
        )
        
    except KeyboardInterrupt:
        print("\n⚠️  Sync interrupted by user")
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
