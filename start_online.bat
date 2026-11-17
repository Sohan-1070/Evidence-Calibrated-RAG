@echo off
echo ========================================================
echo                ECRAG ONLINE STARTUP SCRIPT
echo ========================================================
echo.
echo Starting ECRAG in Online Mode with Gemini and 7-Stage Verification...
echo.

set ECRAG_GEMINI_MODEL=gemini-3.5-flash-lite
set ECRAG_OFFLINE=0

python -m streamlit run app.py

pause
