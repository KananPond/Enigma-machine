@echo off
rem ============================================================
rem  ENIGMA . M3  --  double click to start the machine
rem ============================================================
setlocal
cd /d "%~dp0"

if exist ".venv\Scripts\python.exe" (
  set "PY=.venv\Scripts\python.exe"
  set "PYW=.venv\Scripts\pythonw.exe"
) else (
  set "PY=python"
  set "PYW=pythonw"
)

rem 破译功能需要 numpy，缺了就先装一次（只装一次）
"%PY%" -c "import numpy" 2>nul
if errorlevel 1 (
  echo Installing numpy, this happens once ...
  "%PY%" -m pip install --quiet --disable-pip-version-check numpy
)

rem 用 pythonw 启动，不开控制台窗口；启动失败会弹出错误框
start "" "%PYW%" run.py
endlocal
