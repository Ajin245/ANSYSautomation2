@echo off
setlocal EnableExtensions

rem ==========================================================================
rem  run_ansys.bat - batch run of Mechanical in ANSYS Workbench 21R1.
rem
rem  Delivery channel: the ACT extension src\act\ansys_automation\. The journal
rem  opens the project, calls Refresh + Update and waits for results.csv; no
rem  command is sent into Mechanical (the previous channel silently did nothing
rem  on build 21.1.0.2020110819).
rem
rem  Usage:
rem      scripts\run_ansys.bat "C:\path\project.wbpj" 8946 [08]
rem
rem  Arguments:
rem      1 - project .wbpj path (required)
rem      2 - structure id, exported as STRUCTURE_ID (required)
rem      3 - execution, exported as EXECUTION (optional)
rem
rem  Environment:
rem      ANSYS_WB_EXE     - full path to runwb2.exe
rem                         (default C:\Program Files\ANSYS Inc\v211\
rem                          Framework\bin\win64\runwb2.exe)
rem      MECH_SYSTEM_NAME - Mechanical system name (default: the first one)
rem      ANSYS_ACT_WAIT_SECONDS - how long to wait for results.csv after
rem                         Update() (default 300)
rem      ANSYS_ACT_VER    - ACT version directory (default 211, i.e. 21R1)
rem
rem  Exit codes:
rem      0 - runwb2 returned 0, no AUTOMATION-FAILED, AUTOMATION-OK present
rem      2 - runwb2.exe not found (or required arguments missing)
rem      3 - project .wbpj not found
rem      4 - scripts\workbench_journal.py not found
rem      5 - ACT extension is not installed
rem      otherwise - runwb2 exit code, or 1 when AUTOMATION-FAILED is logged
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

rem Repository root = the directory above scripts\.
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

rem The extension is installed into the user ACT directory. Without it nothing
rem runs the pipeline and the journal would just time out waiting for results.
if not defined APPDATA set "APPDATA=%USERPROFILE%\AppData\Roaming"
if not defined ANSYS_ACT_VER set "ANSYS_ACT_VER=211"
if not exist "%APPDATA%\Ansys\v%ANSYS_ACT_VER%\ACT\extensions\ansys_automation.xml" (
    echo ERROR: ACT extension is not installed:
    echo        "%APPDATA%\Ansys\v211\ACT\extensions\ansys_automation.xml"
    echo        Run scripts\install_act_extension.bat once, then repeat.
    exit /b 5
)

if not exist "%ROOT%\logs" mkdir "%ROOT%\logs"

rem Locale-independent timestamp: yyyyMMdd-HHmmss.
set "STAMP="
for /f "usebackq delims=" %%i in (`powershell -NoProfile -Command "Get-Date -Format yyyyMMdd-HHmmss"`) do set "STAMP=%%i"
if not defined STAMP set "STAMP=unknown-%RANDOM%"

set "LOG=%ROOT%\logs\run-%STAMP%.log"
set "ACT_LOG=%ROOT%\logs\act-run.log"

rem ansys_automation.py reads the root from ANSYS_AUTOMATION_ROOT; the RUN flag
rem lets the ACT extension start the pipeline - without it an installed
rem extension stays silent during normal Mechanical work.
set "ANSYS_AUTOMATION_ROOT=%ROOT%"
set "ANSYS_AUTOMATION_RUN=1"
set "STRUCTURE_ID=%STRUCTURE_ID%"
set "EXECUTION=%EXECUTION%"

echo INFO: runwb2     = "%ANSYS_WB_EXE%"
echo INFO: project    = "%PROJECT%"
echo INFO: structure  = %STRUCTURE_ID%
echo INFO: execution  = %EXECUTION%
echo INFO: log        = "%LOG%"
echo.

rem -B batch without UI, -F opens the project, -R plays the journal.
rem The journal raises Mechanical through Refresh+Update; the ACT extension
rem then runs setup -> solve -> results.csv there.
"%ANSYS_WB_EXE%" -B -F "%PROJECT%" -R "%JOURNAL%" > "%LOG%" 2>&1
set "RUN_RC=%ERRORLEVEL%"

echo.
echo EXIT_CODE=%RUN_RC%
echo LOG_FILE=%LOG%
echo --- last 20 log lines ---
powershell -NoProfile -Command "if (Test-Path -LiteralPath '%LOG%') { Get-Content -LiteralPath '%LOG%' -Tail 20 } else { Write-Output '(log file not found)' }"
if exist "%ACT_LOG%" (
    echo --- last 20 lines of logs\act-run.log ---
    powershell -NoProfile -Command "Get-Content -LiteralPath '%ACT_LOG%' -Tail 20"
)
echo -------------------------

set "FAILED="
findstr /C:"AUTOMATION-FAILED" "%LOG%" >nul 2>&1
if not errorlevel 1 set "FAILED=1"
if exist "%ACT_LOG%" (
    findstr /C:"AUTOMATION-FAILED" "%ACT_LOG%" >nul 2>&1
    if not errorlevel 1 set "FAILED=1"
)

set "DONE="
findstr /C:"AUTOMATION-OK" "%LOG%" >nul 2>&1
if not errorlevel 1 set "DONE=1"

if not "%RUN_RC%"=="0" (
    echo RUN-FAILED: runwb2 exited with code %RUN_RC%
    exit /b %RUN_RC%
)
if defined FAILED (
    echo RUN-FAILED: log contains AUTOMATION-FAILED
    exit /b 1
)
if not defined DONE (
    echo RUN-FAILED: no AUTOMATION-OK marker - pipeline did not report success
    exit /b 1
)

echo RUN-OK
exit /b 0
