@echo off
setlocal enabledelayedexpansion

echo ==========================================
echo Patel Stores Admin - Windows EXE Builder
echo ==========================================

cd /d "%~dp0"

if not exist "release" mkdir "release"

set "PYTHON_EXE="
if exist ".venv\Scripts\python.exe" set "PYTHON_EXE=.venv\Scripts\python.exe"
if "%PYTHON_EXE%"=="" if exist ".venv-1\Scripts\python.exe" set "PYTHON_EXE=.venv-1\Scripts\python.exe"
if "%PYTHON_EXE%"=="" set "PYTHON_EXE=C:\Users\SSD\AppData\Local\Programs\Python\Python314\python.exe"
if not exist "%PYTHON_EXE%" set "PYTHON_EXE=python"

echo Using Python: %PYTHON_EXE%

"%PYTHON_EXE%" -m pip show pyinstaller >nul 2>&1
if errorlevel 1 (
  echo Installing PyInstaller...
  "%PYTHON_EXE%" -m pip install pyinstaller
  if errorlevel 1 goto :build_fail
)

"%PYTHON_EXE%" -m pip show pillow >nul 2>&1
if errorlevel 1 (
  echo Installing Pillow...
  "%PYTHON_EXE%" -m pip install pillow
  if errorlevel 1 goto :build_fail
)

echo Generating custom icon...
"%PYTHON_EXE%" -c "from PIL import Image; img=Image.open('images/test.jpg').convert('RGBA'); img.thumbnail((256,256)); img.save('release/PatelStores.ico', format='ICO')"
if errorlevel 1 goto :build_fail

echo Cleaning previous build artifacts...
if exist "build" rmdir /s /q "build"
if exist "dist" rmdir /s /q "dist"
if exist "Patel Stores Admin.spec" del /f /q "Patel Stores Admin.spec"
if exist "release\Patel Stores Admin.exe" del /f /q "release\Patel Stores Admin.exe"

echo Building EXE with PyInstaller...
"%PYTHON_EXE%" -m PyInstaller ^
  --noconfirm ^
  --clean ^
  --onefile ^
  --windowed ^
  --name "Patel Stores Admin" ^
  --icon "release\PatelStores.ico" ^
  --add-data "admin;admin" ^
  --add-data "images;images" ^
  --add-data "products.json;." ^
  --add-data "patelstores.db;." ^
  --add-data "backup;backup" ^
  admin\desktop_app.py
if errorlevel 1 goto :build_fail

echo Copying EXE to release folder...
copy /Y "dist\Patel Stores Admin.exe" "release\Patel Stores Admin.exe" >nul
if errorlevel 1 goto :build_fail

echo Build complete.
echo EXE: release\Patel Stores Admin.exe
exit /b 0

:build_fail
echo Build failed.
exit /b 1
