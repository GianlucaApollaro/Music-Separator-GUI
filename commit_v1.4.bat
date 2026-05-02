@echo off
echo.
echo ===================================================
echo     Preparing Git Commit for v1.4
echo ===================================================
echo.

echo Staging all changes...
git add .

echo.
echo Changes to be committed:
git status -s

echo.
echo Committing changes...
git commit -m "Music Separator v1.4 - The Workflow Update: Peak Normalization (-0.1dBFS), Stereo Downmix, Subfolder Toggle, Silent Stem Deletion, Only Drums Preset, and Instant Playback Preview"

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
