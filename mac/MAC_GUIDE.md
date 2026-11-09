# Project Seeker for Mac

Built from source code updated on November 9, 2026. App version: 0.9.

## Installation

- `ProjectSeeker-0.9-mac-arm64.dmg`: Macs with Apple Silicon chips.
- `ProjectSeeker-0.9-mac-x86_64.dmg`: Macs with Intel processors.

Open the DMG and drag Project Seeker to Applications. The packages use ad hoc signatures, without an Apple Developer ID or notarization. macOS may require permission in System Settings > Privacy & Security > Open Anyway.

## Mac data storage and features

The app stores its data in `~/Library/Application Support/ProjectSeeker`. Original projects and samples are read without being modified. Reviver copies selected sounds to its own data folder. Assistant API keys are stored in macOS Keychain; no keys are included in the package. The assistant does not download models automatically. Sending library metadata to an external provider requires separate consent.

Files and folders open in Finder. FL Studio and Ableton Live open through macOS file associations. Italian, English, French, German, themes, and the current Windows edition's features are retained, with the Mac-specific limitations described below.

Reviver remains in beta and is disabled by default. On Mac, add the Reviver folder manually in FL Studio's File settings; the app does not modify FL Studio's configuration file. Extra search folders are detected by reading `~/Library/Preferences/Image-Line/reg.xml`. This undocumented format still needs testing with a real FL Studio installation. Dragging files to FL Studio, audio formats other than WAV, and DAW file associations also require testing with the actual applications.

## Private GitHub builds

Private repository: [ProjectSeeker-Mac](https://github.com/gatogatoe/ProjectSeeker-Mac).

The `.github/workflows/build_mac.yml` workflow builds natively on GitHub's Mac servers for arm64 and x86_64. It runs reader tests, data and assistant regression tests, Mac and Keychain checks, and JavaScript and translation checks. It verifies the architecture, ad hoc signature, and DMG integrity. Each compiled app is launched with synthetic data to check WKWebView, pages in four languages and three themes, and loading a local WAV through the player. Results are recorded in the build log; packages and SHA-256 checksums are available as private artifacts.

Automated tests on GitHub's servers do not replace installation testing on a personal Mac. Compatibility with macOS versions older than those used by the build servers has not been verified.

To rebuild on GitHub, select Actions > Build Mac > Run workflow. To build on a Mac with Python 3.14 and Node.js installed, run `bash build_mac.sh`.

To run the app from source on a Mac, double-click `start_mac.command`. The first run creates a local Python environment and installs the required dependencies. The Mac icon source is `icon_mac.png`.
