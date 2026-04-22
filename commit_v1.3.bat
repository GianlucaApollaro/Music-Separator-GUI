@echo off
echo.
echo ===================================================
echo     Preparing Git Commit for v1.3
echo ===================================================
echo.

echo Staging all changes...
git add .

echo.
echo Changes to be committed:
git status -s

echo.
echo Committing changes...
git commit -m "Version 1.3 - The Quality of Life Update: Batch Processing, Persistent Settings, UI Responsiveness, and Mac MPS Fixes"

if errorlevel 1 (
    echo.
    echo ERROR: Commit failed or nothing to commit.
    pause
    exit /b 1
)

echo.
echo Pushing changes to remote...
git push

if errorlevel 1 (
    echo.
    echo ERROR: Push failed. Please check your connection or remote repository.
    pause
    exit /b 1
)

echo.
echo ===================================================
echo     Commit and Push Complete!
echo ===================================================
pause
