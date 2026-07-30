@echo off
setlocal EnableExtensions
cd /d "%~dp0"

echo ============================================
echo NITEOS CONCEPT LIGHT - EXE BUILD
echo ============================================
echo.

set "PYTHON_CMD="

where py >nul 2>nul
if not errorlevel 1 (
    set "PYTHON_CMD=py -3"
) else (
    where python >nul 2>nul
    if not errorlevel 1 (
        set "PYTHON_CMD=python"
    )
)

if "%PYTHON_CMD%"=="" (
    echo ERROR: Python was not found.
    echo Install Python 3.11 or 3.12 and enable "Add Python to PATH".
    echo.
    pause
    exit /b 1
)

echo Python command: %PYTHON_CMD%
echo.

if exist ".venv\Scripts\python.exe" (
    echo Virtual environment found.
) else (
    if exist ".venv" (
        echo Removing broken .venv folder...
        rmdir /s /q ".venv"
    )
    echo Creating virtual environment...
    %PYTHON_CMD% -m venv .venv
    if errorlevel 1 (
        echo ERROR: failed to create virtual environment.
        pause
        exit /b 1
    )
)

call ".venv\Scripts\activate.bat"
if errorlevel 1 (
    echo ERROR: failed to activate virtual environment.
    pause
    exit /b 1
)

echo.
echo Upgrading pip...
python -m pip install --upgrade pip
if errorlevel 1 (
    echo ERROR: pip upgrade failed.
    pause
    exit /b 1
)

echo.
echo Installing dependencies...
pip install -r requirements_exe.txt
if errorlevel 1 (
    echo ERROR: dependency installation failed.
    pause
    exit /b 1
)

echo.
echo Building EXE with PyInstaller...
pyinstaller --noconfirm --clean NITEOS_Concept_Light.spec
if errorlevel 1 (
    echo ERROR: PyInstaller build failed.
    pause
    exit /b 1
)

echo.
echo ============================================
echo BUILD COMPLETE
echo ============================================
echo Portable app folder:
echo dist\NITEOS_Concept_Light
echo.
echo Run:
echo dist\NITEOS_Concept_Light\NITEOS_Concept_Light.exe
echo.

if exist "dist\NITEOS_Concept_Light" (
    explorer "dist\NITEOS_Concept_Light"
)

pause
endlocal
