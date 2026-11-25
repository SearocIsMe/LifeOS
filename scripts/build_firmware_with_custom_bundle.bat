@echo off
REM Rebuild the xiaozhi-esp32 firmware with the extra trust root in certs/.
REM See docs/Deployment.md 附十三 and xiaozhi-esp32-2.5.2/certs/README.md
setlocal

set "IDF_PATH=C:\esp-all\.espressif\v6.1\esp-idf"
set "IDF_TOOLS_PATH=C:\Espressif"
set "IDF_PYTHON_ENV_PATH=C:\Espressif\tools\python_env\idf6.1_py3.12_env"
set "PYTHON=%IDF_PYTHON_ENV_PATH%\Scripts\python.exe"

echo [1/4] checking python env
if not exist "%PYTHON%" (
    echo ERROR: "%PYTHON%" not found
    exit /b 1
)
"%PYTHON%" --version

echo [2/4] removing stale bundle artifacts
pushd "%~dp0.."
if exist "build\x509_crt_bundle" del /q "build\x509_crt_bundle"
if exist "build\x509_crt_bundle.S" del /q "build\x509_crt_bundle.S"

echo [3/4] building
"%PYTHON%" "%IDF_PATH%\tools\idf.py" build
set "RC=%ERRORLEVEL%"
popd

echo [4/4] build exit code = %RC%
if not "%RC%"=="0" (
    echo BUILD FAILED
    exit /b %RC%
)
echo BUILD OK
exit /b 0
