# HTML Templates Documentation

This document provides an overview of all HTML templates included in the MAL Sonarr Sync web application.

## Template Structure

### Base Template
- **`base.html`** - Main layout template with navigation, footer, and common scripts
  - Bootstrap 5.3.0 styling
  - Font Awesome 6.4.0 icons
  - Responsive navigation bar
  - Flash message support
  - Connection status checking
  - Auto-refresh functionality

### Main Application Templates

#### Core Pages
- **`index.html`** - Main dashboard with sync controls and status
  - Connection status indicators for Sonarr and MAL
  - Configuration check and warning
  - Sync action buttons (Preview, Dry Run, Sync Now)
  - Results display with match scores and status badges
  - Sonarr anime list viewer
  - Real-time progress tracking

- **`config.html`** - Configuration page for Sonarr and MAL settings
  - Sonarr API configuration (URL and API key)
  - MyAnimeList OAuth configuration (Client ID and Secret)
  - Sync settings (default status, match thresholds)
  - Form validation and password visibility toggles
  - Helpful setup instructions

- **`about.html`** - Information page about the application
  - Feature overview and how-it-works explanation
  - FAQ section with common questions
  - Match score guidelines
  - Quick links to external resources

#### Utility Templates
- **`status.html`** - Generic status/results page
  - Flexible status display (success, warning, error, info)
  - Detailed sync results with expandable sections
  - Progress indicators and badge counters
  - Navigation back to dashboard

- **`loading.html`** - Loading/processing page for long operations
  - Animated spinner and progress bar
  - Operation status and estimated time
  - Auto-refresh functionality for session tracking
  - Fallback timeout handling

### Error Handling Templates

#### Error Pages (`errors/` directory)
- **`404.html`** - Page not found error
  - Clean 404 error display
  - Navigation links back to main sections

- **`500.html`** - Internal server error
  - Server error explanation
  - Troubleshooting suggestions
  - Configuration check recommendations

- **`error.html`** - Generic error template
  - Flexible error display with customizable content
  - Error details in debug mode
  - Standard navigation options

## Features Implemented

### Responsive Design
- Bootstrap 5.3.0 for mobile-first responsive layout
- Collapsible navigation for mobile devices
- Card-based layout for better organization
- Responsive grid system for all screen sizes

### User Experience
- Loading spinners for all async operations
- Real-time connection status indicators
- Flash message system for user feedback
- Confirmation dialogs for destructive actions
- Auto-refresh functionality for live updates

### Visual Design
- Consistent color scheme with status indicators
- Icon usage throughout (Font Awesome)
- Progress bars and badges for visual feedback
- Syntax highlighting for configuration display
- Clean, modern card-based layout

### Interactive Elements
- Collapsible sections (accordions)
- Toggle buttons for password visibility
- Dynamic content loading via JavaScript
- Form validation and error handling
- Modal dialogs and confirmations

### Accessibility
- Semantic HTML structure
- ARIA labels for screen readers
- Keyboard navigation support
- High contrast status indicators
- Descriptive alt text and labels

## JavaScript Functionality

### Connection Monitoring
- Real-time status checking every 30 seconds
- Visual indicators (green/red dots)
- Error message display

### Sync Operations
- Dry run and preview functionality
- Real-time progress tracking
- Result display with match scoring
- Operation status polling

### Form Handling
- Client-side validation
- Password visibility toggles
- Dynamic form updates
- Configuration preview

### Navigation
- Responsive navbar collapse
- Active page highlighting
- Breadcrumb navigation
- Back button functionality

## Template Variables

### Global Variables (available in all templates)
- `request` - Flask request object
- `url_for` - URL generation function
- `get_flashed_messages` - Flash message retrieval

### Page-specific Variables
- **index.html**: `config_exists`, `authenticated`
- **config.html**: `config` (current configuration object)
- **status.html**: `status_type`, `status_title`, `status_message`, etc.
- **error.html**: `error_code`, `error_title`, `error_message`, `error_details`

## Error Handlers Added to app.py

```python
@app.errorhandler(404)
def not_found_error(error):
    return render_template('errors/404.html'), 404

@app.errorhandler(500)
def internal_error(error):
    return render_template('errors/500.html'), 500

@app.errorhandler(Exception)
def handle_exception(e):
    # Comprehensive error handling with debug support
```

## Routes Covered

- `/` - Dashboard (index.html)
- `/config` - Configuration (config.html)
- `/about` - About page (about.html)
- Error handlers for 404, 500, and general exceptions

All templates are now complete and fully functional with the Flask application!