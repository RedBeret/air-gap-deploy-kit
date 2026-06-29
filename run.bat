@echo off
REM air-gap-deploy-kit — Quick start for Windows
REM Requires Python 3.11+

echo [air-gap-deploy-kit] Setting up virtual environment...
python -m venv .venv
call .venv\Scripts\activate.bat

echo [air-gap-deploy-kit] Installing...
pip install -e .

echo.
echo [air-gap-deploy-kit] Done. Run commands:
echo   kit bundle --help
echo   kit deploy --help
echo   kit verify --help
echo   kit manifest --help
echo.
echo Typical workflow:
echo   kit bundle --output-dir .\kit-bundle
echo   REM transfer kit-bundle to air-gapped machine
echo   kit deploy --bundle-dir .\kit-bundle
echo   kit verify
