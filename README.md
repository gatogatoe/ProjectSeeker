# Project Seeker

A free, open-source app to find an old musical idea, hear its audio export and
reopen it in FL Studio or Ableton Live. Browse projects without modifying the
original files. Available in English, Italian, French and German.

## Downloads and installation

- Windows 10/11, 64-bit: run `ProjectSeeker-setup-0.9.exe`. Microsoft Edge WebView2 Runtime is required. The installer works without administrator rights.

- Apple Silicon: use `mac/ProjectSeeker-0.9-mac-arm64.dmg`.
- Intel Mac: use `mac/ProjectSeeker-0.9-mac-x86_64.dmg`.

These published Mac 0.9 builds retain their MIT license. The current Windows release and source archive use GPL-3.0-only. Open the DMG and drag the app to Applications.


**Windows SmartScreen:** You may see "Windows protected your PC" because the installer is not digitally signed. This warning alone does not mean malware was detected. If you downloaded it from this project's official download page and verified its SHA-256 below, select **More info > Run anyway** to continue, if that option is available.

The Windows installer is unsigned. Mac packages use ad hoc signatures without
Apple Developer ID signing or notarization. See the [Mac guide](docs/MAC_GUIDE.md)
for installation limits. Installation on a personal Mac remains to be confirmed;
automated build checks are not a substitute for that test.

Verify downloads against `SHA256SUMS.txt`:

```powershell
Get-FileHash .\ProjectSeeker-setup-0.9.exe -Algorithm SHA256
```

```sh
shasum -a 256 ProjectSeeker-0.9-mac-arm64.dmg
```

## Getting started

Read [Getting started](docs/GETTING_STARTED.md), [search filters](docs/SEARCH_FILTER.md)
and the [optional assistant guide](docs/ASSISTANT.md). The player plays associated
audio exports; it does not render FLP or ALS files. Albums and playlists organize
your view without moving files. Missing-sample matches by filename require checking.
Reviver is optional, beta, and disabled by default.

Scanning and playback work offline. Project Seeker has no account, telemetry or ads.
Optional search buttons open external websites. An external assistant sends messages
to your chosen provider; sharing library metadata requires separate consent.
Your library, preferences and notes stay in the app's data folder. Windows API
keys use your account's encryption; Mac keys use Keychain. Conversations are stored
locally without encryption. No models are downloaded automatically.

## License

Copyright (C) 2026 Gato. Project Seeker is licensed under GPL-3.0-only; see [LICENSE](LICENSE).
You may use, modify and redistribute it, including commercially, under the GPL's conditions.
The app is supplied without warranty. Third-party components retain their own licenses.
See [dependency licenses](docs/DEPENDENCY_LICENSES.md) and [notices](docs/THIRD_PARTY_NOTICES.md).

## Source code and credits

The matching `ProjectSeeker-0.9-source.tar.gz` contains the application source,
synthetic tests and build scripts for both platforms. It excludes personal notes,
credentials and user projects. The extracted root supports `python build_release.py`
on Windows and `bash build_mac.sh` on Mac with the documented dependencies installed.
Distribute the corresponding source alongside binary downloads as required by the GPL.

[PyFLP](https://github.com/demberto/PyFLP), by demberto and contributors, is credited
as a reference for the FLP format; it is GPL version 3 or later. This app currently
uses its own parser without importing PyFLP. Built with pywebview and PyInstaller;
the Windows installer uses Inno Setup. Fonts: Familjen Grotesk and JetBrains Mono.
FL Studio and Ableton Live are trademarks of their respective owners; no affiliation
or endorsement is claimed.
