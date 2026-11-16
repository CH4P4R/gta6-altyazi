@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo === GTA 6 Türkçe Altyazı kurulumu ===
where py >nul 2>nul || (echo Python bulunamadı. python.org'dan Python 3.12 kur ve "Add to PATH" işaretle. & pause & exit /b 1)
if not exist .venv py -3.12 -m venv .venv || py -3 -m venv .venv
call .venv\Scripts\activate.bat
python -m pip install --upgrade pip
pip install -r requirements.txt
rem rapidocr CPU onnxruntime'ı da kurar; GPU sürümünün kazanması için onu kaldırıp GPU'yu yeniden kur
pip uninstall -y onnxruntime
pip install --force-reinstall --no-deps onnxruntime-gpu
rem CUDA 12 + cuDNN 9 kütüphaneleri (ayrıca CUDA kurmana gerek kalmasın)
pip install nvidia-cublas-cu12 nvidia-cudnn-cu12 nvidia-cuda-runtime-cu12
if not exist models\opus-mt-en-tr\model.bin python tools\model_indir.py
echo.
echo Kurulum bitti. Claude anahtarını config.local.yaml'a değil ortam değişkenine koy:
echo     setx ANTHROPIC_API_KEY "anahtarin"
echo Sonra baslat.bat ile çalıştır.
pause
