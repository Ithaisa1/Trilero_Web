@echo off
setlocal ENABLEDELAYEDEXPANSION

REM Build script for Windows - packages the game and creates a ZIP for itch.io
REM Uses PyInstaller in onedir mode and includes the assets folder

pushd "%~dp0"

REM 1) Ensure dependencies
where py >nul 2>nul
if errorlevel 1 (
  echo Python launcher 'py' not found. Ensure Python is installed and 'py' is on PATH.
  goto :end
)

py -m pip install --upgrade pip
py -m pip install -r requirements.txt
py -m pip install pyinstaller

REM 2) Clean previous build
if exist build rmdir /s /q build
if exist dist rmdir /s /q dist
if exist Trilero.spec del /q Trilero.spec

REM 3) Build with PyInstaller (onedir)
py -m PyInstaller --clean --onedir --noconsole --name Trilero --add-data "assets;assets" main.py
if errorlevel 1 (
  echo PyInstaller failed.
  goto :end
)

REM 4) Create ZIP for distribution (itch.io)
set ZIP_OUT=dist\Trilero-Windows.zip
if exist "%ZIP_OUT%" del /q "%ZIP_OUT%"

REM Small delay to allow file handles to be released
timeout /t 2 /nobreak >nul

REM Prefer tar (built-in on recent Windows) for robustness
where tar >nul 2>nul
if %errorlevel%==0 (
  tar -a -c -f "%ZIP_OUT%" -C "dist\Trilero" .
  if errorlevel 1 goto :zip_fallback
) else (
  goto :zip_fallback
)

goto :zip_done

:zip_fallback
echo tar not available or failed, falling back to PowerShell Compress-Archive
for /l %%i in (1,1,3) do (
  powershell -NoProfile -ExecutionPolicy Bypass -Command "Compress-Archive -Path 'dist/Trilero/*' -DestinationPath 'dist/Trilero-Windows.zip' -Force" && goto :zip_done
  echo Retry %%i failed, waiting...
  timeout /t 2 /nobreak >nul
)
echo Zip step failed. You can zip manually the folder dist\Trilero.
goto :end

:zip_done

echo.
echo Build finished.
echo Folder: dist\Trilero
echo ZIP:    dist\Trilero-Windows.zip

echo.
echo Next steps:
echo - Test the EXE by running dist\Trilero\Trilero.exe
echo - Upload the ZIP to itch.io (or use butler)

echo.
:end
popd
endlocal
