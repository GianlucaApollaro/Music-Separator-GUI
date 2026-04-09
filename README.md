# Music-Separator-GUI 🎶

**Music-Separator-GUI** is a cross-platform (Windows & macOS) graphical interface for high-quality audio stem separation. It is powered by the excellent `python-audio-separator` engine and uses state-of-the-art models from the **Ultimate Vocal Remover** project.

## Features ✨

- **High-Quality Separation**: Extract Vocals, Instrumental, Drums, Bass, Piano, Guitar, and more.
- **Support for Advanced Models**: Compatible with **Roformer**, **MDX-Net**, **VR Arch**, and **Demucs** architectures.
- **User-Friendly Interface**: Easy-to-use GUI built with `wxPython`.
- **Multilingual Support**: The interface is available in **English**, **Italian**, and **Spanish**.
- **Auto-Download**: Models are automatically downloaded on first use.
- **Ensemble Mode**: Combine multiple models for even better results.
- **Cross-Platform**: Native builds available for Windows and macOS (including Apple Silicon).

## Installation and Usage 🚀

### Windows
1. Download the latest version from the [Releases](https://github.com/GianlucaApollaro/Music-Separator-GUI/releases) page.
2. Run `install.bat` once to set up the environment (required for source run) or just run the executable if using the bundled version.
3. Run `run.bat` or the `.exe` to start the application.

### macOS
1. Ensure you have Python installed.
2. Run `install_mac.sh` to set up dependencies.
3. Run `run_mac.sh` to launch the application.

## Credits and Acknowledgments 🙏

This project is a wrapper around several amazing open-source projects. Heartfelt thanks to:

- **Andrew Beveridge** ([beveradb](https://github.com/beveradb)): Author of [python-audio-separator](https://github.com/karaokenerds/python-audio-separator), the engine behind this GUI.
- **Anjok07** & **aufr33**: Developers of the [Ultimate Vocal Remover GUI](https://github.com/Anjok07/ultimatevocalremovergui) and the incredible models (MDX-Net, VR Arch, etc.) that make this possible.
- **Kuielab & Woosung Choi**: For the original MDX-Net AI code.
- **Ivo De Palma**: A special thanks for his invaluable help in debugging and compiling the native macOS version of this application.
- **All model contributors** mentioned in the UVR and audio-separator projects.

## License 📄

This project is licensed under the **MIT License** - see the [LICENSE](LICENSE) file for details. Please respect the licenses of the underlying models and the `audio-separator` library when using or redistributing.
      
