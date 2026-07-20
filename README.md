# Music Separator GUI

[![License](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
[![Donate](https://img.shields.io/badge/Donate-PayPal-green.svg)](https://paypal.me/gianlucaapollaro1)
[![Platform](https://img.shields.io/badge/platform-Windows%20%7C%20macOS-lightgrey.svg)](#)

**Music Separator GUI** is a premium, cross-platform (Windows & macOS) graphical interface designed for high-quality audio stem separation. It is powered by the excellent `python-audio-separator` engine and utilizes state-of-the-art AI models from the **Ultimate Vocal Remover (UVR)** project.

Whether you need to isolate vocals for karaoke, extract instrumentals for remixes, or split a drum kit into individual components, Music Separator GUI offers a native, fast, and accessible solution.

---

## Features

- **Precision Separation**: Extract Vocals, Instrumentals, Drums, Bass, Piano, Guitar, and other instruments.
- **Advanced AI Architectures**: Compatible with **Roformer (BS-Roformer, Mel-Band Roformer)**, **MDX-Net**, **VR Arch**, and **Demucs**.
- **User-Customizable Presets (New in v1.6)**: 
  - Create single-model or multi-pass chained pipelines.
  - Custom output rename suffixes and selective stem discarding via a checklist grid.
  - Save configurations locally in the program root for absolute portability.
- **Native Ensemble Mode**: Merge the outputs of two different models (using algorithms like `avg_wave`, `min_wave`, `max_wave`, or `median_wave`) for cleaner stems.
- **Performance & Out-of-Memory Prevention**: Built-in GPU acceleration support (CUDA on Windows, MPS on Apple Silicon) and **Chunking** option to process long tracks without crashes.
- **Batch Processing**: Drag & drop multiple audio files or entire folders to process them in batch mode.
- **Fully Accessible UI**: Designed with native OS widgets ensuring compatibility with screen readers (NVDA on Windows, VoiceOver on macOS).
- **Multilingual Support**: Available in **English**, **Italian**, and **Spanish**.

---

## Support the Project

If you love this tool and want to support its ongoing development, feel free to buy me a coffee! Your donations help keep the project alive, cover hosting costs, and fund testing on hardware.

**[Support the project on PayPal](https://paypal.me/gianlucaapollaro1)**

---

## AI-Powered Development (Vibe Coding)

This project is built using **AI-assisted pair programming (Vibe Coding)**. 

By pairing the main developer's vision and domain knowledge with advanced, agentic AI coding assistants, we have been able to:
- Code, test, and package complex features (like the dynamic preset creator grid and automated test suites) with extreme speed.
- Maintain rigorous standards for code quality, syntax checking, and multi-platform parity.
- Deliver native macOS compatibility and robust screen reader accessibility features.

---

## Installation and Usage

### Windows

Download the latest `.7z` archive from the [Releases](https://github.com/GianlucaApollaro/Music-Separator-GUI/releases) page.

- **GPU Version** (Recommended) — Requires an NVIDIA GPU with CUDA support.
- **CPU Version** — Works on any PC, but is significantly slower.

#### Precompiled (No Python Required)
1. Extract the archive to a folder of your choice.
2. Run `Music Separator.exe` (GPU) or `Music Separator CPU.exe` (CPU) to launch the app directly.

#### Run from Source
1. Clone the repository or extract the source ZIP.
2. Run `install.bat` (GPU) or `install_cpu.bat` (CPU) **once** to set up the virtual environment and install all dependencies.
3. Launch the application using `run.bat` (GPU) or `run_Cpu.bat` (CPU).

---

### macOS (Apple Silicon — M1/M2/M3/M4)

#### Option A — Compiled App Bundle (Recommended, No Python Required)
1. Download the `Music_Separator_GUI_vX.X_Mac.zip` archive from the [Releases](https://github.com/GianlucaApollaro/Music-Separator-GUI/releases) page.
2. **Important — do not extract directly into `/Applications`.**  
   Create a dedicated subfolder first (e.g. `/Applications/Music Separator/`) and extract the **entire contents** of the `.zip` archive into it.  
   > *Note: The app bundle ships alongside support files (FFmpeg binaries, resources, etc.) that must stay in the same directory as the `.app`. Placing only the `.app` in `/Applications` will break the application.*
3. Open the subfolder, **right-click** the `Music separator.app` file and choose **Open** to bypass macOS Gatekeeper (first launch only).
4. On subsequent launches, you can double-click the `.app` normally.

#### Option B — Run from Source
1. Ensure you have the **Xcode Command Line Tools** installed — open Terminal and run:
   ```bash
   xcode-select --install
   ```
2. Download or clone the repository.
3. **Right-click** `install_mac.command` and choose **Open** to set up the virtual environment and install all dependencies.
4. Launch the app by right-clicking `run_mac.command` and choosing **Open** (first time only), or double-clicking it on subsequent runs.

---

## Credits and Acknowledgments

This project is a wrapper around several amazing open-source projects. Heartfelt thanks to:

- **Andrew Beveridge** ([beveradb](https://github.com/beveradb)): Author of [python-audio-separator](https://github.com/karaokenerds/python-audio-separator), the engine behind this GUI.
- **Anjok07** & **aufr33**: Developers of the [Ultimate Vocal Remover GUI](https://github.com/Anjok07/ultimatevocalremovergui) and the incredible models (MDX-Net, VR Arch, etc.) that make this possible.
- **Kuielab & Woosung Choi**: For the original MDX-Net AI code.
- **GaboxR67**: For the advanced custom models integrated in v1.3 (Instrumental V10, Experimental Inst_Fv8, Lead Vocal Dereverb, Last BS Roformer).
- **Ivo De Palma**: A special thanks for his invaluable help in debugging and compiling the native macOS version of this application.
- **All model contributors** mentioned in the UVR and audio-separator projects.

---

## License

This project is licensed under the **MIT License** - see the [LICENSE](LICENSE) file for details. Please respect the licenses of the underlying models and the `audio-separator` library when using or redistributing.
