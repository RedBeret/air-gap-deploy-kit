@echo off
REM air-gap-deploy-kit — Quick start for Windows
REM Requires Python 3.12+

echo [air-gap-deploy-kit] Setting up virtual environment...
python -m venv .venv
call .venv\Scripts\activate.bat

echo [air-gap-deploy-kit] Installing...
pip install -e .

echo.
echo [air-gap-deploy-kit] Done. Run commands:
echo   kit bundle --help
echo   kit deploy --help
echo   kit rehearse --help
echo   kit verify --help
echo   kit manifest --help
echo.
echo Build a wheelhouse first, then see:
echo   kit bundle --help
