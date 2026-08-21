# Third-Party Notices

daVIPA incorporates the third-party components listed below. Each remains
under its own licence, which governs that component. Nothing in `LICENSE`
limits any right those licences grant you.

Every entry was read from the installed distribution's own package metadata, not
from memory. `tests/test_release_licensing.py` fails if a dependency is added to
`requirements.txt` without a notice here.

## Runtime dependencies

| Component | Version | Licence | Project |
|---|---|---|---|
| CustomTkinter | 5.2.2 | MIT | https://customtkinter.tomschimansky.com |
| pygame | 2.6.1 | **LGPL** — see below | https://www.pygame.org |
| python-dotenv | 1.2.1 | BSD-3-Clause | https://github.com/theskumar/python-dotenv |
| platformdirs | 4.5.1 | MIT | https://github.com/tox-dev/platformdirs |
| Pillow | 12.1.0 | MIT-CMU | https://python-pillow.org |
| pyobjc-framework-Cocoa (macOS only) | 12.2.1 | MIT | https://github.com/ronaldoussoren/pyobjc |
| google-auth | 2.47.0 | Apache-2.0 | https://github.com/googleapis/google-auth-library-python |
| google-auth-oauthlib | 1.2.4 | Apache-2.0 | https://github.com/GoogleCloudPlatform/google-auth-library-python-oauthlib |
| google-auth-httplib2 | 0.3.0 | Apache-2.0 | https://github.com/GoogleCloudPlatform/google-auth-library-python-httplib2 |
| google-api-python-client | 2.188.0 | Apache-2.0 | https://github.com/googleapis/google-api-python-client |
| tzlocal | 5.3.1 | MIT | https://github.com/regebro/tzlocal |

Python itself, and its standard library (including `tkinter` and `sqlite3`), are
distributed under the Python Software Foundation License:
https://docs.python.org/3/license.html

SQLite is in the public domain: https://www.sqlite.org/copyright.html

## Development-only dependencies

Not distributed in the binaries; listed for completeness.

| Component | Version | Licence |
|---|---|---|
| pytest | 9.0.2 | MIT |
| pytest-cov | 7.0.0 | MIT |
| PyInstaller | build tool | GPL-2.0 **with a bootloader exception** that permits distributing the packaged application under any licence |

## pygame — LGPL notice and relink statement

daVIPA links **pygame**, which is distributed under the GNU Lesser General
Public Licence (LGPL), version 2.1. A verbatim copy of that licence — the one
pygame itself ships — is distributed inside every release archive:

- macOS: `daVIPA.app/Contents/Resources/licenses/pygame-LGPL-2.1.txt`
- Windows: `licenses\pygame-LGPL-2.1.txt`, beside `daVIPA.exe`

It is also available at https://www.gnu.org/licenses/lgpl-2.1.html

In accordance with that licence, daVIPA is distributed in **one-folder**
form rather than as a single self-extracting executable, so that pygame's
libraries remain separate, replaceable files. You may replace the pygame
libraries inside the application folder with a modified or different compatible
version and continue to run daVIPA.

- macOS: `daVIPA.app/Contents/Resources/pygame/`
- Windows: `daVIPA\_internal\pygame\`

This packaging choice is enforced by
`tests/test_packaging_resources.py::test_rm1d_spec_uses_onefolder_not_onefile`,
so it cannot be changed to `--onefile` without a test failing.

pygame is used only for optional background-music playback during timer
sessions. No audio files are distributed with daVIPA; you supply your own
music folder in Settings.

## Fonts, icons, and audio

No third-party fonts or audio files are distributed with daVIPA. Icons in
`assets/` are the copyright holder's own work.
