@echo off
setlocal
cd /d %~dp0

echo ================================
echo 建立免安裝 EXE（PyInstaller）
echo ================================

where py >nul 2>nul
if %errorlevel%==0 (
    set PY_CMD=py
) else (
    where python >nul 2>nul
    if %errorlevel%==0 (
        set PY_CMD=python
    ) else (
        echo 找不到 Python，請先在此電腦安裝 Python 3。
        pause
        exit /b 1
    )
)

if not exist venv (
    echo 建立虛擬環境中...
    %PY_CMD% -m venv venv
)

call venv\Scripts\activate.bat
if %errorlevel% neq 0 (
    echo 無法啟用虛擬環境。
    pause
    exit /b 1
)

echo 安裝 / 更新套件（含 PyInstaller）...
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python -m pip install pyinstaller

echo 產生 EXE 中...
pyinstaller --noconfirm --clean --onefile --add-data "templates;templates" --add-data "static;static" app.py

echo --------------------------------
echo 完成！EXE 位於 dist\app.exe
if exist dist\app.exe (
  echo 可將 dist\app.exe 複製到其他 Windows 機器直接使用。
) else (
  echo 未找到 dist\app.exe，請檢查終端機錯誤訊息。
)

echo.
pause
endlocal
