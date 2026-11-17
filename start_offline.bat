@echo off
echo ========================================================
echo               ECRAG OFFLINE STARTUP SCRIPT
echo ========================================================
echo.

:: 1. Start Ollama in the background silently
echo [1/3] Starting Ollama server (if not already running)...
start /B ollama serve >nul 2>&1

:: Wait a few seconds for Ollama to spin up
timeout /t 3 /nobreak >nul

:: 2. Check if the local database has been built yet
echo.
echo [2/3] Checking local offline database...
if not exist "data\chroma_db" (
    echo Local database not found! Building it now...
    python build_offline_db.py
    echo Database built successfully.
) else (
    echo Local database already exists. Skipping build.
)

:: 3. Start the Streamlit application
echo.
echo [3/3] Starting ECRAG Interface...
:: Default to Offline/Island Mode so the app answers from the local
:: ChromaDB + local model without needing internet. Unset this to go online.
set ECRAG_OFFLINE=1
python -m streamlit run app.py

pause
