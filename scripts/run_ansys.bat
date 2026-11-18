@echo off
setlocal EnableExtensions

rem ==========================================================================
rem  run_ansys.bat - batch-прогон Mechanical в ANSYS Workbench 21R1.
rem
rem  Использование:
rem      scripts\run_ansys.bat "C:\path\project.wbpj" 8946 [08]
rem
rem  Аргументы:
rem      1 - путь к проекту .wbpj (обязательный)
rem      2 - ID конструкции, попадает в STRUCTURE_ID (обязательный)
rem      3 - исполнение, попадает в EXECUTION (необязательный)
rem
rem  Переменные окружения:
rem      ANSYS_WB_EXE  - полный путь к runwb2.exe
rem                      (по умолчанию C:\Program Files\ANSYS Inc\v211\
rem                       Framework\bin\win64\runwb2.exe)
rem      MECH_SYSTEM_NAME - имя Mechanical-системы (иначе первая)
rem
rem  Коды возврата:
rem      0 - runwb2 вернул 0 и в логе нет AUTOMATION-FAILED
rem      2 - runwb2.exe не найден (или не заданы обязательные аргументы)
rem      3 - не найден .wbpj
rem      4 - не найден scripts\workbench_journal.py
rem      иначе - код возврата runwb2, либо 1 при маркере AUTOMATION-FAILED
rem ==========================================================================

set "PROJECT=%~1"
set "STRUCTURE_ID=%~2"
set "EXECUTION=%~3"

if "%PROJECT%"=="" (
    echo ERROR: usage: run_ansys.bat ^<project.wbpj^> ^<structure_id^> [execution]
    exit /b 2
)
if "%STRUCTURE_ID%"=="" (
    echo ERROR: structure id is required: run_ansys.bat ^<project.wbpj^> ^<structure_id^> [execution]
    exit /b 2
)

rem Корень репозитория = каталог на уровень выше scripts\.
for %%I in ("%~dp0..") do set "ROOT=%%~fI"
for %%I in ("%PROJECT%") do set "PROJECT=%%~fI"

if not defined ANSYS_WB_EXE set "ANSYS_WB_EXE=C:\Program Files\ANSYS Inc\v211\Framework\bin\win64\runwb2.exe"

if not exist "%ANSYS_WB_EXE%" (
    echo ERROR: runwb2.exe not found: "%ANSYS_WB_EXE%"
    echo        Set ANSYS_WB_EXE to the full path of runwb2.exe for your ANSYS install.
    exit /b 2
)

if not exist "%PROJECT%" (
    echo ERROR: project file not found: "%PROJECT%"
    exit /b 3
)

set "JOURNAL=%ROOT%\scripts\workbench_journal.py"
if not exist "%JOURNAL%" (
    echo ERROR: journal not found: "%JOURNAL%"
    exit /b 4
)

if not exist "%ROOT%\logs" mkdir "%ROOT%\logs"

rem Метка времени без зависимости от локали: yyyyMMdd-HHmmss.
set "STAMP="
for /f "usebackq delims=" %%i in (`powershell -NoProfile -Command "Get-Date -Format yyyyMMdd-HHmmss"`) do set "STAMP=%%i"
if not defined STAMP set "STAMP=unknown-%RANDOM%"

set "LOG=%ROOT%\logs\run-%STAMP%.log"

rem ansys_automation.py читает корень из ANSYS_AUTOMATION_ROOT.
set "ANSYS_AUTOMATION_ROOT=%ROOT%"
set "ANSYS_PROJECT_PATH=%PROJECT%"
set "STRUCTURE_ID=%STRUCTURE_ID%"
set "EXECUTION=%EXECUTION%"

echo INFO: runwb2     = "%ANSYS_WB_EXE%"
echo INFO: project    = "%PROJECT%"
echo INFO: structure  = %STRUCTURE_ID%
echo INFO: execution  = %EXECUTION%
echo INFO: log        = "%LOG%"
echo.

rem -B batch без UI, -F открыть проект, -R проиграть журнал.
"%ANSYS_WB_EXE%" -B -F "%PROJECT%" -R "%JOURNAL%" > "%LOG%" 2>&1
set "RUN_RC=%ERRORLEVEL%"

echo.
echo EXIT_CODE=%RUN_RC%
echo LOG_FILE=%LOG%
echo --- last 20 log lines ---
powershell -NoProfile -Command "if (Test-Path -LiteralPath '%LOG%') { Get-Content -LiteralPath '%LOG%' -Tail 20 } else { Write-Output '(log file not found)' }"
echo -------------------------

set "FAILED="
findstr /C:"AUTOMATION-FAILED" "%LOG%" >nul 2>&1
if not errorlevel 1 set "FAILED=1"

if not "%RUN_RC%"=="0" (
    echo RUN-FAILED: runwb2 exited with code %RUN_RC%
    exit /b %RUN_RC%
)
if defined FAILED (
    echo RUN-FAILED: log contains AUTOMATION-FAILED
    exit /b 1
)

echo RUN-OK
exit /b 0
