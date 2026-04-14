@echo off
setlocal
chcp 65001 >nul

echo ===================================================
echo     Publishing Music Separator GUI v1.2
echo ===================================================

echo.
echo [1] Adding changes to Git...
git add .

echo.
echo [2] Committing changes...
git commit -m "v1.2: Triple Chain & Ultimate Drum Split Update" -m "- The 'Ultimate Stems + Drum Split' 7+ Stems Preset" -m "- Guitar Extraction and Vocal Split Improvements" -m "- Output subdirectories and prefix stripping" -m "- Roformer loading shape mismatch fixes"

echo.
echo [3] Pushing to Repository...
git push origin HEAD

echo.
echo [4] Creating GitHub Release v1.2...

echo Creating Release Notes file...
(
echo This major update brings massive improvements to the internal separation engine, introduces highly requested presets, and resolves critical bugs for third-party custom models.
echo.
echo ### What's New
echo * **The "Ultimate Stems + Drum Split" Preset:** A monumental 3-stage extraction chain ^(Deux ➔ BS-Roformer-SW ➔ MDX23C-DrumSep^). It separates the track into 7+ distinct stems including individual drum components ^(Kick, Snare, Hi-hat, Cymbals, Toms^) while also preserving the primary stereo Drums stem. 
echo * **Guitar Extraction ^& Vocal Split Overhaul:** 
echo   * Re-engineered the Vocal Split preset ^(Frazer ➔ Deux^), achieving far superior isolation for Lead and Backing vocals.
echo   * Added the new **"Guitar Extraction ^(3 Stems^)"** preset that elegantly isolates High-Quality Vocals, Guitar, and the remainder of the Instrumental track.
echo * **Organized Output Flow:** Extracted stems are now automatically stored within dedicated folders named after the source audio. A new optional setting allows you to strip leading track numbers for a perfectly clean workspace.
echo * **Triple-Chain Engine:** The backend has been upgraded to support pipelines that feed stems up through 3 separate model passes sequentially, without deleting intermediate target stems.
echo.
echo ### Bug Fixes ^& Under the Hood Enhancements
echo * **Configuration Parsing Bypass:** Prevented YAML serialization crashes with audio-separator tuple/dict constraints using dedicated fallback PyYaml constructors.
echo * Corrected broken HTTP links for automatic model downloads.
echo.
echo *A huge thanks to the model creators ^(Aufr33, Becruily, Jarredou, VIPERx, ZFTurbo^) for allowing these powerful chained presets to exist!*
) > release_notes_v1.2.md

echo.
echo Verifying release files...
set FILES_TO_UPLOAD=
if exist "Music_Separator_GUI_v1.2_Mac.zip" (
    set FILES_TO_UPLOAD=!FILES_TO_UPLOAD! "Music_Separator_GUI_v1.2_Mac.zip"
    echo Found: Music_Separator_GUI_v1.2_Mac.zip
) else (
    echo WARNING: Music_Separator_GUI_v1.2_Mac.zip NOT FOUND!
)

if exist "Music_Separator_GUI_v1.2_Windows_GPU.7z" (
    set FILES_TO_UPLOAD=!FILES_TO_UPLOAD! "Music_Separator_GUI_v1.2_Windows_GPU.7z"
    echo Found: Music_Separator_GUI_v1.2_Windows_GPU.7z
) else (
    echo WARNING: Music_Separator_GUI_v1.2_Windows_GPU.7z NOT FOUND!
)

if exist "Music_Separator_GUI_v1.2_Windows_CPU.7z" (
    set FILES_TO_UPLOAD=!FILES_TO_UPLOAD! "Music_Separator_GUI_v1.2_Windows_CPU.7z"
    echo Found: Music_Separator_GUI_v1.2_Windows_CPU.7z
) else (
    echo WARNING: Music_Separator_GUI_v1.2_Windows_CPU.7z NOT FOUND!
)

echo.
echo Creating release using GitHub CLI...
gh release create v1.2 %FILES_TO_UPLOAD% --title "Music Separator v1.2 - The Ultimate Stems Update!" --notes-file release_notes_v1.2.md

echo.
echo Cleaning up temporary files...
del release_notes_v1.2.md

echo.
echo ===================================================
echo     Publishing Complete!
echo ===================================================
pause
