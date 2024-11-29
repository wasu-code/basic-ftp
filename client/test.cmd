@echo off
setlocal EnableDelayedExpansion

REM Define the array of commands
set c[1]=python usftp.py mkdir ftp://tst:pass@localhost:21/ newdir
set c[2]=python usftp.py ls ftp://tst:pass@localhost:21/
set c[3]=python usftp.py cp ./ftptest.txt ftp://tst:pass@localhost:21/newdir
set c[4]=python usftp.py cp ftp://tst:pass@localhost:21/newdir/ftptest.txt ./
set c[5]=python usftp.py rm ftp://tst:pass@localhost:21/newdir ftptest.txt

REM Check for a command-line argument
if "%1" neq "" (
    REM Validate the argument
    if not defined c[%1%] (
        echo Invalid choice: %1.
        goto menu
    )
    REM Execute the command directly
    call !c[%1%]!
    goto end
)

:menu
cls
REM Display the list of commands
set i=1
for /F "tokens=2 delims==" %%a in ('set c[') do (
    echo !i!. %%a
    set /a i+=1
)

REM Get user selection
set /p choice="Enter your choice: "

REM Validate user input
if not defined c[%choice%] (
    echo Invalid choice. Please try again.
    pause
    goto menu
)

REM Execute the selected command
call !c[%choice%]!
goto end

:end
