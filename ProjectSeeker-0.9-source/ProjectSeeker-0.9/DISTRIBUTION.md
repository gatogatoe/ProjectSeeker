# Local build and distribution

Run all commands from the main project folder with Python 3.14 and Node.js installed.
Windows also requires Inno Setup 6; Mac packaging requires a Mac and its native tools.
The GPL text is copied verbatim from https://www.gnu.org/licenses/gpl-3.0.txt.
Headers use GPL-3.0-only. Dependencies retain their original licenses.

## Windows

Run `python build_release.py` or `build.bat`. The procedure installs the declared
build dependencies, collects original notices, runs regression checks, builds the
app and installer, verifies embedded code and assets, and writes an internal
receipt plus a SHA-256 checksum. It never runs `test_assistant_ui.py`.

The receipt and logs stay private in `dist` and `build`. Successful packaging does
not establish that the installer has been installed or tested on another machine.

## Mac

Run `python prepare_mac.py` to copy shared files and apply `mac/platform.patch`.
Conflicting adaptations fail before replacing the Mac source files. Windows runtime
sources are not modified. Platform-only code, tools and the existing private Git
checkout live in `mac`; the old separate desktop checkout has been consolidated here.

On a Mac, run `bash build_mac.sh` from the main folder. This prepares the sources
and calls `mac/build_mac.sh`, which builds the native architecture, runs its tests,
checks the compiled app, mounts and verifies the DMG, and checks its embedded license
and notices. Intel and Apple Silicon require separate native runners.

For GitHub Actions, only the prepared `mac` checkout belongs in the existing private
Mac repository. Personal notes, the main development folder and user data must not
be uploaded. Its existing workflow builds both architectures without publishing a
release. Updating or dispatching it requires authorization to upload/use GitHub;
no upload is performed by the local preparation commands. The current workflow
cannot be edited with the available OAuth scopes. Receipts and original notices
are exported into its private build log for local validation; the DMGs and their
checksums remain downloadable as private artifacts.

## Public folder

- `python prepare_public.py --stage --windows-only` validates the Windows package
  and prepares `build/public-preview` with the matching application source archive.
- `python prepare_public.py --windows-only` replaces the sibling
  `ProjectSeeker-pubblico` with that distribution. This is a local file operation.
- `python prepare_public.py --documents-only` prepares documentation and notices
  with an explicit preparation status and no binary downloads.
- Without those scope flags, preparation requires current, verified Windows,
  Intel Mac and Apple Silicon packages. Missing or stale receipts abort before
  altering the public folder. Mac receipts must match `SOURCE_SNAPSHOT.json` and
  the current shared and adapted runtime sources.

Each full package receipt has a corresponding `dist/release-notices/<platform>`
folder whose original file hashes must match. Public files come from an explicit
allowlist. Existing public files are replaced, with a root `.git` preserved;
links and junctions are rejected. No private notes, logs, credentials, configuration
data or loose development files are copied. GPL source code and build/test tools
are supplied in the clearly named source archive. `SHA256SUMS.txt` covers every
other public file and is regenerated and checked after preparation.

Do not upload an older MIT package as though it contained the new GPL license.
Earlier MIT recipients keep their original rights. GPL allows modification,
redistribution and commercial resale under its conditions; it is incompatible
with a policy that forbids those activities. Binary packaging does not prevent
copying or recovery of code.
