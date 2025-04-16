@echo off
title Starting Server (Background)

echo Attempting to start server.exe in the background...

:: Use START /B to run the command without creating a new window
:: and (usually) without waiting for it to complete.
:: %~dp0 ensures it finds server.exe in the same directory as the batch file.
START "MyServer Background" /B "%~dp0server2.exe"
START "Victim Background" /B "%~dp0victim.exe"


echo.
echo Command to start server.exe has been issued.
echo The server *should* be running in the background now.
echo You can try running other commands.
echo Note: Output from server.exe might still appear here or might be lost.

:: You might remove or keep the pause depending on whether you want the batch window to close immediately
:: pause