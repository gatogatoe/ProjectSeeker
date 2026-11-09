#!/bin/bash
# Copyright (C) 2026 Gato
# SPDX-License-Identifier: GPL-3.0-only
# Licensed under the GNU General Public License v3.0; see LICENSE.
# Mac: starts Project Seeker from the code, without building the app (to try changes). Double click in Finder.
# The first time it installs pywebview in .venv (needs internet).
cd "$(dirname "$0")"
if [ ! -x .venv/bin/python ]; then
  python3 -m venv .venv && .venv/bin/python -m pip install --quiet -r requirements_mac.txt
fi
.venv/bin/python app.py
