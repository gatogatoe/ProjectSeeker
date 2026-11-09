Project Seeker

Build the app and Windows installer: build.bat
Open the synthetic 20,000-project load test: load_test.bat

Read README.md and docs/GETTING_STARTED.md for setup and daily use.
See docs/ASSISTANT.md for the optional assistant and its privacy rules.
See docs/SEARCH_FILTER.md for search syntax and the JSON filter format.

The player plays associated audio exports, not FLP or ALS project files.
Albums and playlists organize the view without moving files.
Reviver is optional, beta, and disabled by default.
Unknown values appear as a dash rather than zero. Filename matches are
candidates to verify, not proof that two sounds are identical.

Original projects and samples are opened only for reading. App data is stored
in %APPDATA%\ProjectSeeker, including preferences, metadata, collections,
listening counts, local chats, cover copies, and Reviver sound copies.
API keys use Windows account encryption; chat history is not encrypted.
Link to FL, when explicitly requested in Reviver, changes FL Studio's extra
search folders in the Windows registry. Unlink removes that folder entry.
The app does not edit your project files or move, rename, or delete originals.

Unsigned Windows installers may trigger SmartScreen. Check the release's
signing status and SHA-256 checksum. Windows may offer More info > Run anyway.
Uninstalling preserves the app data folder.
