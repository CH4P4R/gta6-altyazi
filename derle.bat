@echo off
rem GTA6 Altyazı kurulum dosyasını bu bilgisayarda derler (GitHub Actions'ın yaptığının aynısı).
rem Gerekenler: Python 3.12 (python.org, "Add to PATH") ve Inno Setup 6 (jrsoftware.org).
chcp 65001 >nul
setlocal
cd /d "%~dp0"
set PYTHONUTF8=1
set PYTHONIOENCODING=utf-8

where py >nul 2>nul || (echo Python bulunamadı. python.org'dan Python 3.12 kur ve "Add to PATH" işaretle. & pause & exit /b 1)
set ISCC=%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe
if not exist "%ISCC%" set ISCC=%ProgramFiles%\Inno Setup 6\ISCC.exe
if not exist "%ISCC%" (
  echo Inno Setup bulunamadı, kuruluyor...
  winget install -e --id JRSoftware.InnoSetup --accept-package-agreements --accept-source-agreements
  set ISCC=%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe
)

echo === 1/6 Derleme ortamı ===
if not exist .venv-derle py -3.12 -m venv .venv-derle || py -3 -m venv .venv-derle
call .venv-derle\Scripts\activate.bat
python -m pip install --upgrade pip
pip install numpy opencv-python pyyaml rapidfuzz PySide6-Essentials ctranslate2 sentencepiece windows-capture sounddevice anthropic requests segno paramiko pyinstaller pillow pyclipper shapely six || goto hata
pip install --no-deps rapidocr_onnxruntime || goto hata
pip install onnxruntime-directml nvidia-cublas-cu12 || goto hata

echo === 2/6 Çeviri modeli ===
if not exist models\opus-mt-en-tr\model.bin python tools\model_indir.py || goto hata

echo === 3/6 İngilizce OCR modeli ===
python tools\ocr_model_indir.py || goto hata

echo === 4/6 adb ===
if not exist tools\platform-tools\adb.exe (
  powershell -NoProfile -Command "Invoke-WebRequest https://dl.google.com/android/repository/platform-tools-latest-windows.zip -OutFile tools\pt.zip; Expand-Archive -Force tools\pt.zip tools; Remove-Item tools\pt.zip" || goto hata
)

echo === 5/6 Paketleme (birkaç dakika) ===
python packaging\make_assets.py || goto hata
python tools\tv_web_hazirla.py || goto hata
pyinstaller --noconfirm --clean packaging\gta6altyazi.spec || goto hata

echo === 6/6 Kurulum dosyası (5-10 dakika) ===
for /f %%v in ('python -c "import altyazi; print(altyazi.__version__)"') do set VER=%%v
"%ISCC%" /DAppVersion=%VER% packaging\installer.iss || goto hata

echo.
echo Hazır: dist\GTA6Altyazi-Setup.exe
explorer dist
pause
exit /b 0

:hata
echo.
echo Bir adım başarısız oldu. Yukarıdaki hata mesajının ekran görüntüsünü at.
pause
exit /b 1
