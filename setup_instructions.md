# Flask Web App for MAL Sonarr Sync

This Flask web application provides a user-friendly interface for your MyAnimeList Sonarr sync script.

## Features

- 🌐 **Web Interface**: Easy-to-use dashboard for managing syncs
- 🔐 **OAuth2 Authentication**: Secure MAL authentication with PKCE
- 👀 **Preview Mode**: See what would be synced before making changes
- 🧪 **Dry Run**: Test sync without adding to MAL
- ⚙️ **Web Configuration**: Configure settings through the web interface
- 📊 **Real-time Status**: Monitor connection status to Sonarr and MAL
- 📈 **Match Scoring**: Visual feedback on title matching confidence
- 🎯 **Smart Filtering**: Only sync high-confidence matches

## Setup Instructions

### 1. Project Structure

Create the following directory structure:

```
mal-sonarr-webapp/
├── app.py                  # Main Flask application
├── requirements.txt        # Python dependencies
├── templates/
│   ├── base.html          # Base template
│   ├── index.html         # Dashboard
│   └── config.html        # Configuration page
├── config.json            # Configuration file (created by app)
└── mal_token.json         # OAuth tokens (auto-generated)
```

### 2. Install Dependencies

```bash
# Create virtual environment (recommended)
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install required packages
pip install -r requirements.txt
```

### 3. Create Template Directory

Create a `templates` directory and add the three HTML files (base.html, index.html, config.html) from the artifacts above.

### 4. MyAnimeList API Setup

1. Go to [MAL API Config](https://myanimelist.net/apiconfig)
2. Click "Create ID"
3. Fill in the application details:
   - **App Name**: Your choice (e.g., "MAL Sonarr Sync")
   - **App Type**: Web
   - **App Description**: Brief description
   - **App Redirect URL**: `http://localhost:5000/callback` (or your domain)
4. Save the Client ID and Client Secret

### 5. Run the Application

```bash
python app.py
```

The web interface will be available at: `http://localhost:5000`

### 6. Configuration

1. Open the web interface
2. Go to the Configuration page
3. Fill in your settings:
   - **Sonarr URL**: Your Sonarr instance URL (e.g., `http://localhost:8989`)
   - **Sonarr API Key**: Found in Sonarr Settings → General
   - **MAL Client ID**: From step 4
   - **MAL Client Secret**: From step 4
   - **Sync Settings**: Adjust match score and default status as needed

### 7. Authentication

1. After saving configuration, return to the Dashboard
2. Click "Authenticate with MAL" 
3. You'll be redirected to MyAnimeList to authorize the app
4. After authorization, you'll be redirected back to the dashboard

## Usage

### Dashboard Features

- **Connection Status**: Shows real-time connection status to Sonarr and MAL
- **Preview Sync**: See what anime would be synced without making changes
- **Dry Run**: Test the full sync process without adding anything to MAL
- **Sync Now**: Perform the actual sync and add matching anime to your MAL list
- **Sonarr Anime List**: View all anime series found in your Sonarr instance

### Sync Process

1. **Detection**: Finds anime in Sonarr (by tags, series type, or title patterns)
2. **Search**: Searches MAL for matching titles
3. **Matching**: Uses fuzzy string matching with multiple algorithms
4. **Filtering**: Only syncs matches above the configured threshold
5. **Status Mapping**: Maps Sonarr status to appropriate MAL status
6. **Sync**: Adds anime to your MAL list with correct status

### Status Mapping

- `continuing` → `watching`
- `ended`/`completed` → `completed`
- Other statuses → Your configured default status

## Configuration Options

### Sync Settings

- **Default MAL Status**: Status to assign to synced anime
- **Minimum Match Score**: Threshold for fuzzy matching (0-100)
- **Auto Sync**: Enable automatic syncing (future feature)
- **Sync Interval**: Hours between automatic syncs

### Match Score Guidelines

- **85%+**: High confidence match (recommended threshold)
- **65-84%**: Medium