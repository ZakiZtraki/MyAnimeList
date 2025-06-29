# MAL-Sonarr Sync

Automatically sync your anime from Sonarr to your MyAnimeList account using OAuth2 Authorization Code Grant with PKCE.

## Features

- 🔐 **Secure OAuth2 Authentication** with PKCE support
- 🎯 **Smart Title Matching** using fuzzy string matching
- 📺 **Sonarr Integration** with tag-based filtering
- ⚙️ **Configurable Options** via JSON configuration
- 🔄 **Token Management** with automatic refresh
- 📊 **Interactive/Non-interactive Modes**
- 🚀 **Dry Run Support** to preview changes

## Prerequisites

1. **Sonarr** instance with API access
2. **MyAnimeList API Application** ([Create one here](https://myanimelist.net/apiconfig))
3. **Python 3.7+**

## Installation

1. Clone this repository:
   ```bash
   git clone <repository-url>
   cd MyAnimeList
   ```

2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

3. Run the setup script:
   ```bash
   python setup.py
   ```

## Configuration

### Automatic Setup
Run the interactive setup:
```bash
python setup.py
```

### Manual Configuration
Create a `config.json` file based on `config.json.template`:

```json
{
    "sonarr": {
        "api_url": "http://localhost:8989/api/v3/series",
        "api_key": "your-sonarr-api-key"
    },
    "mal": {
        "client_id": "your-mal-client-id",
        "client_secret": "your-mal-client-secret",
        "redirect_uri": "http://localhost:8765/callback"
    },
    "sync": {
        "default_status": "completed",
        "minimum_match_score": 75,
        "auto_sync": false,
        "sync_interval_hours": 24
    }
}
```

### MyAnimeList API Setup

1. Go to [MAL API Config](https://myanimelist.net/apiconfig)
2. Click "Create ID"
3. Fill in the application details:
   - **App Name**: Your choice (e.g., "Sonarr Sync")
   - **App Type**: Web
   - **App Description**: Brief description
   - **App Redirect URL**: `http://localhost:8765/callback`
4. Copy the Client ID and Client Secret to your config

### Sonarr Setup

1. In Sonarr, go to **Settings → General**
2. Copy your **API Key**
3. Note your Sonarr URL (usually `http://localhost:8989`)

## Usage

### Basic Usage

```bash
# Dry run to see what would be synced
python sync_mal_sonarr.py --dry-run

# Interactive sync (recommended for first run)
python sync_mal_sonarr.py

# Non-interactive sync
python sync_mal_sonarr.py --non-interactive

# Set default MAL status
python sync_mal_sonarr.py --status watching
```

### Command Line Options

- `--dry-run`: Show what would be synced without making changes
- `--non-interactive`: Run without user prompts
- `--status {watching,completed,on_hold,dropped,plan_to_watch}`: Default MAL status
- `--help`: Show all available options

## How It Works

### Authentication Flow
1. **OAuth2 PKCE**: Uses secure Authorization Code Grant with PKCE
2. **Token Storage**: Saves tokens locally with expiration tracking
3. **Auto Refresh**: Automatically refreshes expired tokens

### Anime Detection
1. **Tag-based**: Finds series with "anime" tags in Sonarr
2. **Type-based**: Identifies anime series types
3. **Title-based**: Fallback detection using title patterns

### Title Matching
1. **Title Cleaning**: Removes season numbers, years, and common suffixes
2. **Fuzzy Matching**: Uses multiple algorithms for best match:
   - Ratio matching
   - Partial ratio matching
   - Token sort ratio (weighted highest)
3. **Multiple Titles**: Checks MAL's main title, English title, Japanese title, and synonyms
4. **Configurable Threshold**: Minimum match score (default: 75%)

### Sync Logic
1. **Duplicate Check**: Verifies if anime is already in your MAL list
2. **Status Mapping**: Maps Sonarr status to MAL status:
   - `continuing` → `watching`
   - `ended`/`completed` → `completed` (or configured default)
3. **Rate Limiting**: Respects API rate limits with delays
4. **Error Handling**: Comprehensive error handling and reporting

## Configuration Options

### Sync Settings

- `default_status`: Default MAL status for synced anime
- `minimum_match_score`: Minimum fuzzy match score (0-100)
- `auto_sync`: Enable automatic syncing (future feature)
- `sync_interval_hours`: Hours between automatic syncs

### MAL Status Options

- `watching`: Currently watching
- `completed`: Finished watching
- `on_hold`: On hold/paused
- `dropped`: Dropped
- `plan_to_watch`: Plan to watch

## Troubleshooting

### Common Issues

1. **"No anime found in Sonarr"**
   - Check if your series have "anime" tags
   - Verify Sonarr API URL and key
   - Check Sonarr accessibility

2. **"Authentication failed"**
   - Verify MAL Client ID and Secret
   - Check redirect URI matches exactly
   - Ensure MAL app is approved

3. **"Low match scores"**
   - Adjust `minimum_match_score` in config
   - Check for special characters in titles
   - Some titles may need manual review

4. **"Rate limited"**
   - The script includes automatic delays
   - Wait a few minutes and try again
   - Consider reducing batch size

### Debug Mode

Enable verbose logging by modifying the script or check the console output for detailed information about:
- API requests and responses
- Title matching scores
- Authentication status
- Rate limiting

## File Structure

```
MyAnimeList/
├── sync_mal_sonarr.py      # Main sync script
├── setup.py                # Interactive setup
├── config.json.template    # Configuration template
├── config.json             # Your configuration (created by setup)
├── mal_token.json          # OAuth tokens (auto-generated)
├── requirements.txt        # Python dependencies
└── README.md              # This file
```

## Security Notes

- **API Keys**: Keep your Sonarr API key and MAL credentials secure
- **Token Storage**: OAuth tokens are stored locally in `mal_token.json`
- **HTTPS**: Use HTTPS for production Sonarr instances
- **Firewall**: The script temporarily opens port 8765 for OAuth callback

## References
- [MyAnimeList API Docs](https://myanimelist.net/apiconfig/references/api/v2)
- [MyAnimeList OAuth2](https://myanimelist.net/apiconfig/references/authorization)  
- [Sonarr API Docs](https://sonarr.tv/docs/api/)

## License
See [API Agreement](https://myanimelist.net/static/apiagreement.html) for MyAnimeList usage terms.
