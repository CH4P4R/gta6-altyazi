#!/bin/bash
# SPDX-License-Identifier: AGPL-3.0-only
# chiaki-ng kaynaklarını (CouchSubs'ın kullandığı sabit sürüm) native/chiaki-ng'ye indirir ve yamaları uygular.
set -euo pipefail
cd "$(dirname "$0")"
COMMIT="$(tr -d ' \r\n' < CHIAKI_COMMIT)"
if [[ ! -d chiaki-ng/.git ]]; then
  git -c core.autocrlf=false clone --filter=blob:none https://github.com/chiaki-ng/chiaki-ng.git chiaki-ng
fi
git -C chiaki-ng -c core.autocrlf=false checkout -q --force "$COMMIT"
git -C chiaki-ng -c core.autocrlf=false submodule update --init --depth 1 \
  third-party/nanopb third-party/jerasure third-party/gf-complete third-party/curl
for p in patches/chiaki-*.patch; do
  if git -C chiaki-ng apply --reverse --check "../$p" 2>/dev/null; then
    echo "Zaten uygulanmış: $p"
  else
    git -C chiaki-ng apply "../$p"
    echo "Uygulandı: $p"
  fi
done
