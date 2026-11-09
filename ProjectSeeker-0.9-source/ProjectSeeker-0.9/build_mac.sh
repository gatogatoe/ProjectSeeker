#!/bin/bash
# Copyright (C) 2026 Gato
# SPDX-License-Identifier: GPL-3.0-only
# Licensed under the GNU General Public License v3.0; see LICENSE.
set -euo pipefail
cd "$(dirname "$0")"
"${PYTHON:-python3}" prepare_mac.py
exec bash mac/build_mac.sh
