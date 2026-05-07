# Release Notes - v1.4

This version introduces significant improvements in audio preprocessing and new file management options for a cleaner and more professional workflow.

### New Features
- **Automatic Normalization**: All input files are now normalized to **-0.1 dBFS** before processing. This ensures that AI models always receive an optimal volume signal, improving separation accuracy without the risk of clipping.
- **Automatic Stereo Downmix**: Added native support for multichannel files (e.g., **5.1, 7.1**). The program automatically downmixes to stereo before separation.
- **"Play Stem" Button**: You can now instantly play the generated stems directly from the application. After separation, just click "Play Stem" and select the desired track to open it in the system player.
- **New "Only Drums" Preset**: Added a dedicated preset using the BS-Roformer-SW model to extract exclusively percussion, automatically removing all other instruments for a clean output folder.
- **Naming Improvement**: When the "Use Subfolder" option is disabled, the program now automatically adds the original filename as a prefix to the stems. This prevents accidental overwrites when processing multiple songs in the same folder.
- **UI Optimization**: Reorganized the options layout for better readability and graphic alignment.
- **"Use Subfolder" Option**: You can now choose whether to save files in a dedicated subfolder (default behavior) or directly in the selected output folder (legacy behavior).
- **Silent Stem Deletion**: New option to automatically remove output files that are silent (below -50 dB), useful for keeping the workspace clean when using models that generate many stems.

### Improvements and Fixes
- Optimized initial file conversion via FFmpeg to better support complex video and audio streams.
- Improved temporary file management to avoid conflicts during batch processing.
- Updated user manuals (IT, EN, ES) with new instructions for Windows and macOS.
- Fixed a bug in preset configuration persistence.

---
**Note for macOS users**: Make sure to move the application to the `/Applications` folder before starting it to ensure correct loading of support components.
