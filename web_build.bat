@echo off
setlocal ENABLEDELAYEDEXPANSION

REM Build HTML5 (WebAssembly) with pygbag and zip for itch.io
pushd "%~dp0"

where py >nul 2>nul
if errorlevel 1 (
  echo Python launcher 'py' not found. Open this script from a terminal where Python is on PATH.
  goto :end
)

REM 1) Ensure pygbag
py -m pip install --upgrade pip
py -m pip install pygbag

REM 2) Build web (clean previous)
if exist build rmdir /s /q build
py -m pygbag --build .
if errorlevel 1 (
  echo pygbag build failed.
  goto :end
)

REM 2.1) Ensure pygbag archives are installed LOCALLY (requires app dir with main.py)
py -m pygbag --install 0.9 "%CD%"

REM 2.2) Copy pygbag archives into build/web to avoid 404 with http.server
set SRCARCH=%USERPROFILE%\.pygbag\archives
set DSTARCH=build\web\archives
if exist "%SRCARCH%" (
  if not exist "%DSTARCH%" mkdir "%DSTARCH%"
  where robocopy >nul 2>nul
  if %errorlevel%==0 (
    robocopy "%SRCARCH%" "%DSTARCH%" /E >nul
  ) else (
    xcopy /E /I /Y "%SRCARCH%" "%DSTARCH%" >nul
  )
) else (
  echo WARNING: Local pygbag archives not found at %SRCARCH%.
)

REM 2.3) Force absolute CDN URLs in index.html (backup in case archives missing)
if exist build\web\index.html (
  powershell -NoProfile -ExecutionPolicy Bypass -Command "(Get-Content 'build/web/index.html') 
    -replace '="\/archives\/','="https://pygame-web.github.io/archives/' 
    -replace '\/\/archives\/','https://pygame-web.github.io/archives/' 
    -replace 'https://pygame-web.github.io/archives//','https://pygame-web.github.io/archives/' 
    | Set-Content 'build/web/index.html' -Encoding UTF8"
)

REM 3) Create ZIP with content of build/web (index.html must be at the root of the zip)
set WEBFOLDER=build\web
set ZIP_OUT=build\web.zip
if not exist "%WEBFOLDER%\index.html" (
  echo ERROR: build\web\index.html not found. Build may have failed.
  goto :end
)
if exist "%ZIP_OUT%" del /q "%ZIP_OUT%"
powershell -NoProfile -ExecutionPolicy Bypass -Command "Compress-Archive -Path '%WEBFOLDER%/*' -DestinationPath '%ZIP_OUT%' -Force"

if errorlevel 1 (
  echo Zip step failed. You can zip manually the contents of build\web.
  goto :end
)

echo.
echo Web build finished.
echo Folder: build\web

echo ZIP ready for itch.io (HTML): build\web.zip

echo.
echo To test locally, run:
echo     py -m http.server 8000 -d build\web

echo And open: http://localhost:8000

echo.
:end
popd
endlocal
