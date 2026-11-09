# Project Seeker for Mac

Choose the arm64 DMG for Apple Silicon or x86_64 for Intel. Open it and drag
Project Seeker to Applications. The packages use ad hoc signatures without an
Apple Developer ID or notarization. macOS may require permission in System Settings
> Privacy & Security > Open Anyway. Only proceed with a download you trust and
whose checksum you have verified.

The app stores data in `~/Library/Application Support/ProjectSeeker`. API keys use
macOS Keychain. Original projects and samples are read without modification.
The player plays associated audio exports, not FLP or ALS files. Projects open
through macOS file associations; folders open in Finder.

Reviver is beta and disabled by default. Add its folder manually in FL Studio's
File settings. The app does not change FL Studio's configuration file. Detection
of existing search folders uses an undocumented format that still needs validation
with a real FL Studio installation.

Installation on a personal Mac, real DAW associations, drag-to-FL behavior and
audio codecs beyond the synthetic WAV check have not been confirmed. Compatibility
with older macOS versions than the build runners has not been verified.

Copyright (C) 2026 Gato. Project Seeker is licensed under GPL version 3; see
`LICENSE` in the DMG and the application resources. Third-party licenses and
notices are included separately and keep their original terms. The corresponding
source archive accompanies the binary downloads.
