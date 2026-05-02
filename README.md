# Music-Separator-GUI

**Music-Separator-GUI** is a cross-platform (Windows & macOS) graphical interface for high-quality audio stem separation. It is powered by the excellent `python-audio-separator` engine and uses state-of-the-art models from the **Ultimate Vocal Remover** project.

## Features

- **High-Quality Separation**: Extract Vocals, Instrumental, Drums, Bass, Piano, Guitar, and more.
- **Support for Advanced Models**: Compatible with **Roformer**, **MDX-Net**, **VR Arch**, and **Demucs** architectures.
- **User-Friendly Interface**: Easy-to-use GUI built with `wxPython`.
- **Multilingual Support**: The interface is available in **English**, **Italian**, and **Spanish**.
- **Auto-Download**: Models are automatically downloaded on first use.
- **Ensemble Mode**: Combine multiple models for even better results.
- **Chained Presets**: Multi-pass processing pipelines for advanced stem extraction (7+ tracks, Drum Split, De-Reverb, and more).
- **Batch Processing**: Process entire folders of audio files in one go.
- **Cross-Platform**: Native builds available for Windows and macOS (including Apple Silicon).

## Installation and Usage

### Windows

Download the latest `.7z` archive from the [Releases](https://github.com/GianlucaApollaro/Music-Separator-GUI/releases) page. Two builds are available:

- **GPU version** (recommended) — requires an NVIDIA GPU with CUDA support.
- **CPU version** — works on any PC, but is significantly slower.

#### Precompiled (no Python required)

1. Extract the archive to a folder of your choice.
2. Run `Music Separator.exe` (GPU) or `Music Separator CPU.exe` (CPU) to start the application directly.

#### Run from Source

1. Extract the archive or clone the repository.
2. Run `install.bat` (GPU) or `install_cpu.bat` (CPU) **once** to set up the virtual environment and install all dependencies.
3. Launch the application with `run.bat` (GPU) or `run_Cpu.bat` (CPU).

---

### macOS (Apple Silicon — M1/M2/M3/M4)

Two options are available for macOS:

#### Option A — Compiled App Bundle (recommended, no Python required)

1. Download the `Music_Separator_GUI_vX.X_Mac.zip` archive from the [Releases](https://github.com/GianlucaApollaro/Music-Separator-GUI/releases) page.
2. **Important — do not extract directly into `/Applications`.**  
   Create a dedicated subfolder first (e.g. `/Applications/Music Separator/`) and extract the **entire contents** of the `.zip` archive into it.  
   > The app bundle ships alongside support files (FFmpeg binaries, resources, etc.) that must stay in the same directory as the `.app`. Placing only the `.app` in `/Applications` — or mixing its files with other apps — will prevent the application from working correctly.
3. Open the subfolder, **right-click** the `.app` file and choose **Open**. This step is required the first time to bypass macOS Gatekeeper (the app is not notarized).
4. On subsequent launches you can double-click the `.app` normally.

#### Option B — Run from Source

1. Ensure you have the **Xcode Command Line Tools** installed — open Terminal and run:
   ```
   xcode-select --install
   ```
2. Download or clone the repository.
3. **Right-click** `install_mac.command` and choose **Open** to set up the virtual environment and install all dependencies.
4. Launch the app by right-clicking `run_mac.command` and choosing **Open** (first time only), or double-clicking it on subsequent runs.

> **Note**: As of v1.3, FFmpeg binaries are bundled with the Mac package, so installing them via Homebrew is no longer required.

---

## Credits and Acknowledgments

This project is a wrapper around several amazing open-source projects. Heartfelt thanks to:

- **Andrew Beveridge** ([beveradb](https://github.com/beveradb)): Author of [python-audio-separator](https://github.com/karaokenerds/python-audio-separator), the engine behind this GUI.
- **Anjok07** & **aufr33**: Developers of the [Ultimate Vocal Remover GUI](https://github.com/Anjok07/ultimatevocalremovergui) and the incredible models (MDX-Net, VR Arch, etc.) that make this possible.
- **Kuielab & Woosung Choi**: For the original MDX-Net AI code.
- **GaboxR67**: For the advanced custom models integrated in v1.3 (Instrumental V10, Experimental Inst_Fv8, Lead Vocal Dereverb, Last BS Roformer).
- **Ivo De Palma**: A special thanks for his invaluable help in debugging and compiling the native macOS version of this application.
- **All model contributors** mentioned in the UVR and audio-separator projects.

## License

This project is licensed under the **MIT License** - see the [LICENSE](LICENSE) file for details. Please respect the licenses of the underlying models and the `audio-separator` library when using or redistributing.
