@echo off
REM Rebuild the xiaozhi-esp32 firmware with the extra trust root in certs/.
REM See docs/Deployment.md 附十三 and xiaozhi-esp32-2.5.2/certs/README.md
setlocal

set "IDF_PATH=C:\esp-all\.espressif\v6.1\esp-idf"
REM IDF_TOOLS_PATH must be the directory that holds espidf.constraints.v6.1.txt
REM and python_env\ -- that is C:\Espressif\tools, NOT C:\Espressif.
set "IDF_TOOLS_PATH=C:\Espressif\tools"
set "IDF_PYTHON_ENV_PATH=C:\Espressif\tools\python_env\idf6.1_py3.12_env"
set "PYTHON=%IDF_PYTHON_ENV_PATH%\Scripts\python.exe"
REM idf_component_manager reads ESP_IDF_VERSION for its version gates.
REM Skipping export.bat means this is unset -> TypeError in Version.coerce().
REM Keep in sync with the IDF tree in IDF_PATH.
set "ESP_IDF_VERSION=6.1"
set "PYTHONUTF8=1"
chcp 65001 >nul

REM Toolchain: cmake / ninja / xtensa gcc must be on PATH. export.bat normally
REM prepends these, so we do it by hand (idf.py aborts without "cmake").
set "PATH=C:\Espressif\tools\cmake\4.0.3\bin;C:\Espressif\tools\ninja\1.12.1;C:\Espressif\tools\xtensa-esp-elf\esp-15.2.0_20251204\xtensa-esp-elf\bin;C:\Espressif\tools\idf-exe\1.0.3;%PATH%"

echo [1/4] checking python env
if not exist "%PYTHON%" (
    echo ERROR: "%PYTHON%" not found
    exit /b 1
)
"%PYTHON%" --version

echo [2/4] removing stale bundle artifacts
pushd "%~dp0"
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
