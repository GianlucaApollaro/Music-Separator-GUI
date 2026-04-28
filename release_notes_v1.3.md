# Music Separator v1.3 - The Quality of Life Update!

We are excited to release **Version 1.3** of Music Separator! This update is packed with major workflow improvements, new models, persistent settings, and critical fixes for multi-pass processing.

## 🌟 Major Features
- **Persistent User Settings!** The application now remembers all of your choices between sessions. Your output directory, selected models, active preset, and audio format are automatically saved and restored.
- **Batch Processing & Folder Selection:** Process an entire folder of audio files sequentially. Use the new **Browse Folder** button to load directories instantly.
- **New Advanced Presets:**
    - **Ultimate Stems + Drum Split:** Over 10 tracks total, splitting the instrumental into components and then the drums into individual pieces.
    - **Guitar Extraction:** A dedicated preset to isolate the guitar track.
    - **Improved Ultimate Stems:** Now includes an `_Extra` stem for residuals and preserves the full `_Instrumental` without being overwritten by the `_Other` stem.

## 🎵 New Models (GaboxR67 Custom)
Integrated 4 high-quality custom models for professional results:
- **Instrumental V10:** High-fidelity music extraction.
- **Inst_Fv8:** Experimental surgical separation.
- **Lead Vocal Dereverb:** Advanced echo/reverb removal for lead vocals.
- **Last BS Roformer:** State-of-the-art balanced separation.

## ⚡ Performance & UI Improvements
- **Smooth Model Downloads:** UI remains responsive during downloads with background processing.
- **Ensemble Algorithms:** Choose between Average, Min, Max, and Median wave fusion in the manual Ensemble mode.
- **Full Localization:** Complete i18n support for Italian, English, and Spanish across all dialogs, tooltips, and manuals.

## 🍏 Apple Silicon (Mac) Enhancements
- **GPU Acceleration Enabled:** Full support for Apple Silicon MPS (Metal Performance Shaders).
- **Bundled FFmpeg:** No more external dependencies! FFmpeg binaries are now included directly in the macOS package.
- **Graceful OOM Handling:** Clear warnings and suggestions when a model exceeds available unified memory.

## 🐛 Bug Fixes & Polish
- **Stem Naming Logic:** Fixed a critical bug in chained presets where `_Other` could overwrite `_Instrumental`.
- **Robust Model Sync:** Improved handling of the remote model registry to prevent invalid URL warnings.

---
*Happy separating!*
