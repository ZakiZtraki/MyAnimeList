@echo off
echo Installing MAL-Sonarr Sync dependencies...
echo.

pip install requests fuzzywuzzy python-levenshtein flask flask_socketio

echo.
echo Dependencies installed!
echo You can now run the setup script:
echo python setup.py
echo.
pause
