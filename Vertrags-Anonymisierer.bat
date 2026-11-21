@echo off
rem Startet die Weboberflaeche des Vertrags-Anonymisierers.
rem Ohne Umlaute, weil die Eingabeaufforderung sie je nach Codepage verstuemmelt.
setlocal
set "PROJEKT=%~dp0"
set "PROGRAMM=%PROJEKT%.venv\Scripts\vertrags-anonymisierer.exe"

if not exist "%PROGRAMM%" (
  echo.
  echo Der Vertrags-Anonymisierer ist auf diesem Rechner noch nicht eingerichtet.
  echo.
  echo   Erwartet wurde: "%PROGRAMM%"
  echo.
  echo Bitte die Einrichtung aus README.md durchfuehren
  echo ^(python -m venv .venv, .venv\Scripts\pip install -e .^).
  echo.
  pause
  exit /b 1
)

if "%ANTHROPIC_API_KEY%"=="" (
  echo Hinweis: ANTHROPIC_API_KEY ist nicht gesetzt - Senden an Claude ist dann nicht moeglich.
)

cd /d "%PROJEKT%"
if "%~1"=="" (
  "%PROGRAMM%" oberflaeche
) else (
  "%PROGRAMM%" %*
)
if errorlevel 1 pause
