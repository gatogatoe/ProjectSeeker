# Dependency licenses and credits

Project Seeker's original code is licensed under GPL-3.0-only. Independent
components keep their own copyright notices and license terms. Compatibility
means that their terms permit their use in a GPL version 3 distribution when
their respective requirements are met; it does not relicense those components.

## Application and packaging dependencies

| Component | License | GPL version 3 compatibility and conditions |
| --- | --- | --- |
| Python 3.14 | PSF and historical permissive licenses | Compatible; retain the complete license and incorporated-library notices. |
| [pywebview](https://github.com/r0x0r/pywebview/blob/master/LICENSE) 6.2.1 | BSD-3-Clause | Compatible; reproduce copyright, conditions and disclaimer. |
| [Bottle](https://github.com/bottlepy/bottle/blob/master/LICENSE) 0.13.4 | MIT | Compatible; retain the original notice. |
| [proxy_tools](https://github.com/jtushman/proxy_tools/blob/master/LICENSE.txt) 0.1.0 | Upstream BSD-2-Clause; installed metadata says MIT | Both are GPL-compatible. Preserve the complete upstream text and both copyright holders, rather than relying on the metadata label. |
| [typing_extensions](https://github.com/python/typing_extensions/blob/main/LICENSE) 4.16.0 | PSF-2.0 and historical licenses | Compatible; preserve the complete supplied text. |
| [pythonnet](https://github.com/pythonnet/pythonnet/blob/master/LICENSE) 3.2.1 | MIT | Compatible; retain its license and authors list. Windows only. |
| [clr-loader](https://github.com/pythonnet/clr-loader/blob/main/LICENSE) 0.3.1 | MIT | Compatible; retain the original notice. Windows only. |
| [CFFI](https://github.com/python-cffi/cffi/blob/main/LICENSE) 2.1.1 | MIT-0, with separately licensed incorporated code | Compatible; preserve the installed license and libffi notice. |
| [pycparser](https://github.com/eliben/pycparser/blob/main/LICENSE) 3.11 | BSD-3-Clause | Compatible; preserve the original notice. |
| [PyObjC](https://github.com/ronaldoussoren/pyobjc/blob/main/pyobjc-core/License.txt) and its framework wrappers | MIT; libffi separately licensed | Compatible; preserve notices for each installed wrapper and libffi. Mac only. |
| [keyring](https://github.com/jaraco/keyring/blob/v25.7.0/pyproject.toml) 25.7.0 | MIT | Compatible; retain its notice and those of jaraco.classes, jaraco.context, jaraco.functools and more-itertools. Mac only here. |
| [Pillow](https://pillow.readthedocs.io/en/stable/about.html#license) 12.0.0 | MIT-CMU / HPND family and separately licensed codecs | Main license compatible; Mac icon packaging tool, not imported by the app. Retain its complete supplied license; review native codecs if a future package bundles them. |
| [setuptools](https://github.com/pypa/setuptools/blob/main/LICENSE) and its vendored modules | MIT and other permissive licenses | Compatible when the included MIT, BSD, Apache-2.0 and other notices are retained. |
| [packaging](https://github.com/pypa/packaging/tree/main/licenses) | Apache-2.0 OR BSD-2-Clause | Compatible with GPL version 3. Preserve the license files. |
| [PyInstaller](https://pyinstaller.org/en/stable/license.html) 6.22.3 | GPL-2.0-or-later with bootloader distribution exception; some Apache-2.0 files | Compatible. The exception permits distributing application bundles under the application's chosen license. No changes to PyInstaller were made. |
| altgraph, macholib, pefile, pywin32-ctypes | MIT | Compatible; packaging dependencies, with their complete installed notices retained. |
| pyinstaller-hooks-contrib | GPL-2.0-or-later and Apache-2.0 | Compatible with GPL version 3; build hooks retain their original licenses. |
| [Inno Setup](https://jrsoftware.org/files/is/license.txt) | Inno Setup License | A separately licensed installer tool, not linked into our application. It permits distributing installers; preserve its embedded notices and identify it accurately. |
| [Familjen Grotesk](https://github.com/google/fonts/blob/main/ofl/familjengrotesk/OFL.txt), [JetBrains Mono](https://github.com/JetBrains/JetBrainsMono/blob/master/OFL.txt) | SIL OFL-1.1 | May be aggregated with GPL software; fonts remain OFL, not GPL. Preserve their full individual notices and the existing combined notice. |
| [domJSON](https://github.com/azaslavsky/domJSON/blob/master/LICENSE.md) | MIT | Compatible; preserve Alex Zaslavsky's original copyright and license. Included by pywebview. |
| [Microsoft WebView2 SDK](https://www.nuget.org/packages/Microsoft.Web.WebView2/1.0.3856.49) | Microsoft BSD-style redistribution license, plus third-party NOTICE | SDK terms compatible with GPLv3; reproduce both original files. The separately installed WebView2 Runtime is not bundled. |

Python's native dependencies include permissive licenses for OpenSSL (Apache-2.0,
compatible with GPLv3), libffi (MIT), Expat (MIT), bzip2, XZ/liblzma, Zstandard
(BSD option), zlib/zlib-ng, mpdecimal and HACL*. Their actual platform builds,
notices and versions must be checked when packaging. Microsoft runtime components
and native OS frameworks retain their own terms; the GPL does not relicense them.
System libraries are addressed in section 1 of the GPL. No unrestricted relicensing
of Microsoft binaries is claimed.

## PyFLP

[PyFLP](https://github.com/demberto/PyFLP), by demberto and contributors, has the
official GPL version 3 text in `LICENSE`; its source headers explicitly permit
version 3 or any later version (GPL-3.0-or-later). This is compatible with
Project Seeker's GPL-3.0-only choice.

PyFLP 2.2.1 is installed in the development Python environment, but it is absent
from both application requirements files and no current application module
imports it. The current app uses its own FLP parser. PyFLP is credited as a
format/documentation reference; installation alone is not evidence of runtime use.
Its construct-typing, construct and sortedcontainers dependencies are therefore
not application dependencies in this build.

## Distribution obligations

Keep the GPL text, source headers and all third-party notices. Supply the complete
corresponding application source and scripts needed to build each released binary,
with clear access alongside the binary downloads. Private personal notes, API keys,
libraries and music files are not corresponding source and must not be included.
GPL permits modification, redistribution and commercial resale under its conditions.
Copies previously received under MIT keep those permissions; this change does not
revoke them.

Official references: [GNU GPL version 3](https://www.gnu.org/licenses/gpl-3.0.html),
[GNU license compatibility list](https://www.gnu.org/licenses/license-list.html),
[Python licenses](https://docs.python.org/3.14/license.html), and
[OFL bundling FAQ](https://openfontlicense.org/ofl-faq/).
