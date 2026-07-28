@echo off
setlocal enabledelayedexpansion
chcp 65001 >nul
title Auto Catch Pokemon - PGSharp (by Qpham)
cd /d "%~dp0"

set "VENV=%~dp0.venv"
set "PY=%VENV%\Scripts\python.exe"
set "PYW=%VENV%\Scripts\pythonw.exe"

rem ================= 1. Tao moi truong ao neu chua co =================
if exist "%PY%" goto deps

set "BASEPY="
where py >nul 2>&1 && set "BASEPY=py -3"
if not defined BASEPY where python >nul 2>&1 && set "BASEPY=python"
if not defined BASEPY goto nopython

echo [1/3] Dang tao moi truong ao (.venv)... chi lam 1 lan dau tien.
!BASEPY! -m venv "%VENV%"
if not exist "%PY%" (
    echo [LOI] Tao .venv that bai.
    pause
    exit /b 1
)

rem ================= 2. Cai thu vien neu con thieu =================
:deps
"%PY%" -c "import cv2, numpy, av" >nul 2>&1
if not errorlevel 1 goto run

echo [2/3] Dang cai thu vien (opencv, numpy, av)... mat vai phut, vui long doi.
"%PY%" -m pip install --upgrade pip >nul 2>&1
"%PY%" -m pip install -r requirements.txt
if errorlevel 1 goto pipfail
"%PY%" -c "import cv2, numpy, av" >nul 2>&1
if errorlevel 1 goto pipfail

rem ================= 3. Mo giao dien =================
:run
echo [3/3] Dang mo giao dien...
if exist "%PYW%" (
    start "" "%PYW%" "%~dp0gui.py"
    exit /b 0
)
"%PY%" "%~dp0gui.py"
if errorlevel 1 (
    echo.
    echo [LOI] Chuong trinh dung bat thuong. Xem thong bao loi o tren.
    pause
)
exit /b 0

:nopython
echo [LOI] Khong tim thay Python tren may.
echo Tai va cai Python 3.10 tro len tai: https://www.python.org/downloads/
echo Nho tich "Add python.exe to PATH" khi cai dat.
pause
exit /b 1

:pipfail
echo.
echo [LOI] Cai thu vien that bai. Kiem tra ket noi mang roi chay lai file nay.
pause
exit /b 1
