from flask import Flask, render_template, request, jsonify, redirect, url_for, session, flash
import json
import os
import requests
import secrets
import hashlib
import base64
from urllib.parse import urlencode, parse_qs
import threading
import time
from datetime import datetime, timedelta
from fuzzywuzzy import fuzz, process
import re
from flask_socketio import SocketIO, emit
import uuid

app = Flask(__name__)
app.secret_key = secrets.token_hex(16)
socketio = SocketIO(app, cors_allowed_origins="*")

# Configuration
CONFIG_FILE = 'config.json'
TOKEN_FILE = 'mal_token.json'

# Store active sync sessions
active_syncs = {}

class MALSonarrSync:
    def __init__(self):
        self.config = self.load_config()
        self.tokens = self.load_tokens()
        
    def load_config(self):
        """Load configuration from config.json"""
        if os.path.exists(CONFIG_FILE):
            with open(CONFIG_FILE, 'r') as f:
                return json.load(f)
        return {}
    
    def save_config(self, config):
        """Save configuration to config.json"""
        with open(CONFIG_FILE, 'w') as f:
            json.dump(config, f, indent=4)
        self.config = config
    
    def load_tokens(self):
        """Load OAuth tokens from mal_token.json"""
        if os.path.exists(TOKEN_FILE):
            with open(TOKEN_FILE, 'r') as f:
                return json.load(f)
        return {}
    
    def save_tokens(self, tokens):
        """Save OAuth tokens to mal_token.json"""
        with open(TOKEN_FILE, 'w') as f:
            json.dump(tokens, f, indent=4)
        self.tokens = tokens
    
    def generate_pkce_challenge(self):
        """Generate PKCE code verifier and challenge"""
        code_verifier = base64.urlsafe_b64encode(secrets.token_bytes(32)).decode('utf-8').rstrip('=')
        code_challenge = base64.urlsafe_b64encode(
            hashlib.sha256(code_verifier.encode('utf-8')).digest()
        ).decode('utf-8').rstrip('=')
        return code_verifier, code_challenge
    
    def get_auth_url(self):
        """Generate MAL OAuth authorization URL"""
        if not self.config.get('mal', {}).get('client_id'):
            return None
            
        code_verifier, code_challenge = self.generate_pkce_challenge()
        session['code_verifier'] = code_verifier
        
        params = {
            'response_type': 'code',
            'client_id': self.config['mal']['client_id'],
            'code_challenge': code_challenge,
            'code_challenge_method': 'S256',
            'redirect_uri': self.config['mal']['redirect_uri']
        }
        
        return f"https://myanimelist.net/v1/oauth2/authorize?{urlencode(params)}"
    
    def exchange_code_for_token(self, code):
        """Exchange authorization code for access token"""
        token_data = {
            'client_id': self.config['mal']['client_id'],
            'client_secret': self.config['mal']['client_secret'],
            'code': code,
            'code_verifier': session.get('code_verifier'),
            'grant_type': 'authorization_code',
            'redirect_uri': self.config['mal']['redirect_uri']
        }
        
        response = requests.post('https://myanimelist.net/v1/oauth2/token', data=token_data)
        
        if response.status_code == 200:
            tokens = response.json()
            tokens['expires_at'] = time.time() + tokens['expires_in']
            self.save_tokens(tokens)
            return True
        return False
    
    def refresh_token(self):
        """Refresh the access token"""
        if not self.tokens.get('refresh_token'):
            return False
            
        token_data = {
            'client_id': self.config['mal']['client_id'],
            'client_secret': self.config['mal']['client_secret'],
            'grant_type': 'refresh_token',
            'refresh_token': self.tokens['refresh_token']
        }
        
        response = requests.post('https://myanimelist.net/v1/oauth2/token', data=token_data)
        
        if response.status_code == 200:
            tokens = response.json()
            tokens['expires_at'] = time.time() + tokens['expires_in']
            self.save_tokens(tokens)
            return True
        return False
    
    def get_valid_token(self):
        """Get a valid access token, refreshing if necessary"""
        if not self.tokens.get('access_token'):
            return None
        
        expires_at = self.tokens.get('expires_at', 0)
        # Handle ISO string or float
        if isinstance(expires_at, str):
            try:
                expires_at_dt = datetime.fromisoformat(expires_at)
                expires_at_ts = expires_at_dt.timestamp()
            except Exception:
                # fallback: treat as 0 if parsing fails
                expires_at_ts = 0
        else:
            expires_at_ts = float(expires_at)
        
        if time.time() >= expires_at_ts:
            if not self.refresh_token():
                return None
        return self.tokens['access_token']
    
    def get_sonarr_anime(self):
        """Fetch anime series from Sonarr"""
        if not self.config.get('sonarr', {}).get('api_url'):
            print("Sonarr API URL not configured")
            return []
            
        headers = {'X-Api-Key': self.config['sonarr']['api_key']}
        
        try:
            print(f"Fetching series from Sonarr: {self.config['sonarr']['api_url']}")
            response = requests.get(self.config['sonarr']['api_url'], headers=headers)
            
            if response.status_code == 200:
                series = response.json()
                print(f"Found {len(series)} total series in Sonarr")
                
                # Filter for anime series
                anime_series = []
                for show in series:
                    if self.is_anime_series(show):
                        anime_series.append({
                            'title': show.get('title', ''),
                            'year': show.get('year'),
                            'status': show.get('status', ''),
                            'overview': show.get('overview', ''),
                            'sonarr_id': show.get('id'),
                            'path': show.get('path', ''),
                            'tags': show.get('tags', [])
                        })
                
                print(f"Identified {len(anime_series)} anime series")
                return anime_series
            else:
                print(f"Sonarr API returned status code: {response.status_code}")
                print(f"Response content: {response.text}")
                
        except Exception as e:
            print(f"Error fetching Sonarr data: {str(e)}")
            print(f"Full error details: {repr(e)}")
        
        return []
    
    def is_anime_series(self, series):
        """Determine if a series is anime"""
        # Check if the series has tags
        tags = []
        if isinstance(series.get('tags'), list):
            tags = series.get('tags', [])
        elif isinstance(series.get('tags'), str):
            tags = [{'label': tag.strip()} for tag in series.get('tags', '').split(',')]

        # Check tags
        for tag in tags:
            if isinstance(tag, dict) and 'label' in tag:
                if 'anime' in tag['label'].lower():
                    return True
            elif isinstance(tag, str) and 'anime' in tag.lower():
                return True
        
        # Check series type
        series_type = str(series.get('seriesType', '')).lower()
        if 'anime' in series_type:
            return True
        
        # Check path and folder name for anime indicators
        path = str(series.get('path', '')).lower()
        if 'anime' in path:
            return True
            
        # Check title patterns (enhanced heuristic)
        title = str(series.get('title', '')).lower()
        anime_indicators = [
            'anime', 'manga', '-san', '-kun', '-chan', 
            'season', '季', 'の', 'シーズン',
            'japanese', '日本'
        ]
        return any(indicator in title for indicator in anime_indicators)
    
    def clean_title(self, title):
        """Clean title for better matching"""
        # Remove year, season numbers, and common suffixes
        title = re.sub(r'\(\d{4}\)', '', title)  # Remove year
        title = re.sub(r'Season \d+', '', title, flags=re.IGNORECASE)
        title = re.sub(r'S\d+', '', title)  # Remove season markers
        title = re.sub(r'\bOVA\b|\bONA\b|\bSpecial\b', '', title, flags=re.IGNORECASE)
        return title.strip()
    
    def search_mal_anime(self, title, limit=10):
        """Search for anime on MyAnimeList"""
        token = self.get_valid_token()
        if not token:
            return []
        
        headers = {'Authorization': f'Bearer {token}'}
        params = {
            'q': title,
            'limit': limit,
            'fields': 'id,title,alternative_titles,synopsis,status'
        }
        
        try:
            response = requests.get('https://api.myanimelist.net/v2/anime', 
                                  headers=headers, params=params)
            if response.status_code == 200:
                return response.json().get('data', [])
        except Exception as e:
            print(f"Error searching MAL: {e}")
        
        return []
    
    def find_best_match(self, sonarr_title, mal_results):
        """Find the best matching anime using fuzzy matching"""
        if not mal_results:
            return None, 0
        
        cleaned_sonarr = self.clean_title(sonarr_title)
        best_match = None
        best_score = 0
        
        for anime in mal_results:
            anime_data = anime['node']
            titles_to_check = [anime_data['title']]
            
            # Add alternative titles
            alt_titles = anime_data.get('alternative_titles', {})
            titles_to_check.extend(alt_titles.get('synonyms', []))
            if alt_titles.get('en'):
                titles_to_check.append(alt_titles['en'])
            if alt_titles.get('ja'):
                titles_to_check.append(alt_titles['ja'])
            
            # Calculate fuzzy match scores
            for title in titles_to_check:
                if not title:
                    continue
                    
                cleaned_mal = self.clean_title(title)
                
                # Use multiple fuzzy matching algorithms
                ratio_score = fuzz.ratio(cleaned_sonarr.lower(), cleaned_mal.lower())
                partial_score = fuzz.partial_ratio(cleaned_sonarr.lower(), cleaned_mal.lower())
                token_score = fuzz.token_sort_ratio(cleaned_sonarr.lower(), cleaned_mal.lower())
                
                # Weight token sort ratio higher as it's more reliable
                combined_score = (ratio_score + partial_score + token_score * 2) / 4
                
                if combined_score > best_score:
                    best_score = combined_score
                    best_match = anime_data
        
        return best_match, best_score
    
    def get_user_anime_list(self):
        """Get user's anime list from MAL"""
        token = self.get_valid_token()
        if not token:
            return []
        
        headers = {'Authorization': f'Bearer {token}'}
        params = {
            'fields': 'list_status',
            'limit': 1000
        }
        
        try:
            response = requests.get('https://api.myanimelist.net/v2/users/@me/animelist', 
                                  headers=headers, params=params)
            if response.status_code == 200:
                return response.json().get('data', [])
        except Exception as e:
            print(f"Error fetching user anime list: {e}")
        
        return []
    
    def add_anime_to_list(self, anime_id, status='plan_to_watch'):
        """Add anime to user's MAL list"""
        token = self.get_valid_token()
        if not token:
            return False
        
        headers = {'Authorization': f'Bearer {token}'}
        data = {'status': status}
        
        try:
            response = requests.put(f'https://api.myanimelist.net/v2/anime/{anime_id}/my_list_status',
                                  headers=headers, data=data)
            return response.status_code == 200
        except Exception as e:
            print(f"Error adding anime to list: {e}")
            return False

# Initialize the sync class
sync = MALSonarrSync()

@app.route('/')
def index():
    """Main dashboard"""
    return render_template('index.html', 
                         config_exists=bool(sync.config),
                         authenticated=bool(sync.tokens.get('access_token')))

@app.route('/config')
def config():
    """Configuration page"""
    return render_template('config.html', config=sync.config)

@app.route('/about')
def about():
    """About page"""
    return render_template('about.html')

@app.route('/save_config', methods=['POST'])
def save_config():
    """Save configuration"""
    config_data = {
        'sonarr': {
            'api_url': request.form.get('sonarr_url', '').rstrip('/') + '/api/v3/series',
            'api_key': request.form.get('sonarr_key', '')
        },
        'mal': {
            'client_id': request.form.get('mal_client_id', ''),
            'client_secret': request.form.get('mal_client_secret', ''),
            'redirect_uri': request.url_root.rstrip('/') + '/callback'
        },
        'sync': {
            'default_status': request.form.get('default_status', 'completed'),
            'minimum_match_score': int(request.form.get('match_score', 75)),
            'auto_sync': request.form.get('auto_sync') == 'on',
            'sync_interval_hours': int(request.form.get('sync_interval', 24))
        }
    }
    
    sync.save_config(config_data)
    flash('Configuration saved successfully!', 'success')
    return redirect(url_for('config'))

@app.route('/authenticate')
def authenticate():
    """Start MAL OAuth authentication"""
    auth_url = sync.get_auth_url()
    if auth_url:
        return redirect(auth_url)
    else:
        flash('Please configure MAL settings first', 'error')
        return redirect(url_for('config'))

@app.route('/callback')
def callback():
    """Handle OAuth callback"""
    code = request.args.get('code')
    if code and sync.exchange_code_for_token(code):
        flash('Successfully authenticated with MyAnimeList!', 'success')
    else:
        flash('Authentication failed', 'error')
    
    return redirect(url_for('index'))

@app.route('/api/sonarr_anime')
def api_sonarr_anime():
    """API endpoint to get Sonarr anime"""
    anime = sync.get_sonarr_anime()
    return jsonify(anime)

@app.route('/api/sync_preview')
def api_sync_preview():
    """API endpoint to preview sync without making changes"""
    sonarr_anime = sync.get_sonarr_anime()
    user_list = sync.get_user_anime_list()
    
    # Get IDs of anime already in user's list
    existing_ids = {anime['node']['id'] for anime in user_list}
    
    preview_results = []
    min_score = sync.config.get('sync', {}).get('minimum_match_score', 75)
    
    for anime in sonarr_anime:
        mal_results = sync.search_mal_anime(anime['title'])
        best_match, score = sync.find_best_match(anime['title'], mal_results)
        
        result = {
            'sonarr_title': anime['title'],
            'sonarr_status': anime['status'],
            'match_found': best_match is not None,
            'match_score': score,
            'will_sync': score >= min_score and best_match and best_match['id'] not in existing_ids
        }
        
        if best_match:
            result['mal_title'] = best_match['title']
            result['mal_id'] = best_match['id']
            result['already_in_list'] = best_match['id'] in existing_ids
        
        preview_results.append(result)
    
    return jsonify(preview_results)

@app.route('/api/sync', methods=['POST'])
def api_sync():
    """API endpoint to perform actual sync with real-time progress updates"""
    dry_run = request.json.get('dry_run', False)
    session_id = str(uuid.uuid4())
    
    # Store session info
    active_syncs[session_id] = {
        'status': 'starting',
        'current_item': 0,
        'total_items': 0,
        'results': []
    }
    
    def sync_worker():
        try:
            sonarr_anime = sync.get_sonarr_anime()
            user_list = sync.get_user_anime_list()
            
            # Get IDs of anime already in user's list
            existing_ids = {anime['node']['id'] for anime in user_list}
            
            total_items = len(sonarr_anime)
            active_syncs[session_id]['total_items'] = total_items
            
            sync_results = []
            min_score = sync.config.get('sync', {}).get('minimum_match_score', 75)
            default_status = sync.config.get('sync', {}).get('default_status', 'completed')
            
            for i, anime in enumerate(sonarr_anime):
                current_item = i + 1
                active_syncs[session_id]['current_item'] = current_item
                
                # Emit progress update
                socketio.emit('sync_progress', {
                    'session_id': session_id,
                    'title': anime['title'],
                    'current': current_item,
                    'total': total_items,
                    'status': 'processing'
                })
                
                mal_results = sync.search_mal_anime(anime['title'])
                best_match, score = sync.find_best_match(anime['title'], mal_results)
                
                # Determine result status for filtering
                if not best_match:
                    result_status = 'error'  # No match found
                elif score < min_score:
                    result_status = 'warning'  # Match score too low
                elif best_match['id'] in existing_ids:
                    result_status = 'success'  # Already in list (considered success)
                else:
                    result_status = 'success'  # Will be added/was added successfully
                
                result = {
                    'sonarr_title': anime['title'],
                    'success': False,
                    'message': '',
                    'match_score': score,
                    'status': result_status,
                    'mal_title': best_match['title'] if best_match else '',
                    'mal_id': best_match['id'] if best_match else None
                }
                
                if not best_match:
                    result['message'] = 'No match found'
                elif score < min_score:
                    result['message'] = f'Match score too low ({score:.1f}% < {min_score}%)'
                    result['mal_title'] = best_match['title']
                elif best_match['id'] in existing_ids:
                    result['message'] = 'Already in MAL list'
                    result['success'] = True
                else:
                    if dry_run:
                        result['message'] = f'Would add: {best_match["title"]} (Score: {score:.1f}%)'
                        result['success'] = True
                    else:
                        # Map Sonarr status to MAL status
                        mal_status = default_status
                        if anime['status'].lower() == 'continuing':
                            mal_status = 'watching'
                        elif anime['status'].lower() in ['ended', 'completed']:
                            mal_status = 'completed'
                        
                        if sync.add_anime_to_list(best_match['id'], mal_status):
                            result['message'] = f'Added: {best_match["title"]} as {mal_status}'
                            result['success'] = True
                        else:
                            result['message'] = 'Failed to add to MAL'
                            result['status'] = 'error'
                
                sync_results.append(result)
                active_syncs[session_id]['results'] = sync_results
                
                # Add delay to respect rate limits
                if not dry_run:
                    time.sleep(1)
            
            # Emit completion
            socketio.emit('sync_complete', {
                'session_id': session_id,
                'results': sync_results
            })
            
            active_syncs[session_id]['status'] = 'completed'
            
        except Exception as e:
            socketio.emit('sync_error', {
                'session_id': session_id,
                'error': str(e)
            })
            active_syncs[session_id]['status'] = 'error'
    
    # Start sync in background thread
    thread = threading.Thread(target=sync_worker)
    thread.daemon = True
    thread.start()
    
    return jsonify({'session_id': session_id})

@app.route('/api/sync_status/<session_id>')
def api_sync_status(session_id):
    """Get current sync status"""
    if session_id in active_syncs:
        return jsonify(active_syncs[session_id])
    else:
        return jsonify({'error': 'Session not found'}), 404

@app.route('/api/test_connection')
def api_test_connection():
    """Test connections to Sonarr and MAL"""
    results = {
        'sonarr': False,
        'mal': False,
        'messages': {}
    }
    
    # Test Sonarr connection
    try:
        if sync.config.get('sonarr', {}).get('api_url'):
            headers = {'X-Api-Key': sync.config['sonarr']['api_key']}
            response = requests.get(sync.config['sonarr']['api_url'], headers=headers, timeout=10)
            results['sonarr'] = response.status_code == 200
            results['messages']['sonarr'] = 'Connected' if results['sonarr'] else f'Error: {response.status_code}'
        else:
            results['messages']['sonarr'] = 'Not configured'
    except Exception as e:
        results['messages']['sonarr'] = f'Connection failed: {str(e)}'
    
    # Test MAL connection
    try:
        token = sync.get_valid_token()
        if token:
            headers = {'Authorization': f'Bearer {token}'}
            response = requests.get('https://api.myanimelist.net/v2/users/@me', headers=headers, timeout=10)
            results['mal'] = response.status_code == 200
            results['messages']['mal'] = 'Authenticated' if results['mal'] else f'Error: {response.status_code}'
        else:
            results['messages']['mal'] = 'Not authenticated'
    except Exception as e:
        results['messages']['mal'] = f'Connection failed: {str(e)}'
    
    return jsonify(results)

# Error handlers
@app.errorhandler(404)
def not_found_error(error):
    return render_template('errors/404.html'), 404

@app.errorhandler(500)
def internal_error(error):
    return render_template('errors/500.html'), 500

@app.errorhandler(Exception)
def handle_exception(e):
    # Pass through HTTP errors
    if hasattr(e, 'code'):
        return e
    
    # Handle non-HTTP exceptions
    app.logger.error(f'Unhandled exception: {e}')
    return render_template('errors/error.html', 
                         error_code='500',
                         error_title='Internal Server Error',
                         error_message='An unexpected error occurred.',
                         error_details=str(e) if app.debug else None), 500

# WebSocket event handlers
@socketio.on('connect')
def handle_connect():
    print('Client connected')

@socketio.on('disconnect')
def handle_disconnect():
    print('Client disconnected')

if __name__ == '__main__':
    socketio.run(app, debug=True, host='0.0.0.0', port=5000)