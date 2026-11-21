#!/bin/bash
# SPDX-License-Identifier: AGPL-3.0-only
# Yerleşik Remote Play kütüphanesini (couchsubs_native.dylib: libchiaki + FFmpeg) macOS Apple Silicon için derler.
# CouchSubs'ın scripts/build-chiaki-macos.sh betiğinden uyarlandı: Homebrew kütüphaneleri derleyen makinenin macOS'unu
# hedeflediği için (eski macOS'ta açılışta çöker) OpenSSL, json-c, libevent, miniupnpc ve FFmpeg kaynaktan, macOS 13'ü
# hedefleyerek statik derlenir; hepsi tek .dylib'in içine bağlanır (yalnız sistem kütüphanelerine bağlı kalır).
#
#   native/build-mac.sh            -> native/bin/couchsubs_native.dylib
# Gerekenler: Xcode komut satırı araçları, cmake, ninja, python3, internet.
set -euo pipefail
cd "$(dirname "$0")"
NATIVE="$PWD"
SRC="$NATIVE/chiaki-ng"
WORK="$NATIVE/build/mac-work"
PREFIX="$WORK/prefix"
VENV="$WORK/venv"
JOBS="${JOBS:-$(sysctl -n hw.ncpu)}"
MIN="13.0"
ARCH="arm64"
OPENSSL_VERSION="3.5.4"
JSONC_TAG="json-c-0.18-20240915"
FFMPEG_VERSION="7.1.2"

[[ -f "$SRC/lib/CMakeLists.txt" ]] || { echo "HATA: chiaki-ng yok: $SRC (native/fetch-chiaki.sh)" >&2; exit 1; }
mkdir -p "$WORK/archives" "$PREFIX" "$NATIVE/bin"
export MACOSX_DEPLOYMENT_TARGET=$MIN
SYSROOT="$(xcrun --sdk macosx --show-sdk-path)"

if [[ ! -x "$VENV/bin/python3" ]]; then
  python3 -m venv "$VENV"
  "$VENV/bin/pip" install --quiet protobuf grpcio-tools
fi

fetch() {
  local name=$1 url=$2 dir=$3
  [[ -d "$WORK/archives/$name" ]] && return
  curl -fsSL --retry 5 --retry-all-errors --retry-delay 5 "$url" | tar -xz -C "$WORK/archives"
  mv "$WORK/archives/$dir" "$WORK/archives/$name"
}
fetch openssl "https://github.com/openssl/openssl/releases/download/openssl-$OPENSSL_VERSION/openssl-$OPENSSL_VERSION.tar.gz" "openssl-$OPENSSL_VERSION"
fetch json-c "https://codeload.github.com/json-c/json-c/tar.gz/refs/tags/$JSONC_TAG" "json-c-$JSONC_TAG"
fetch libevent https://codeload.github.com/libevent/libevent/tar.gz/refs/tags/release-2.1.12-stable libevent-release-2.1.12-stable
fetch miniupnp https://codeload.github.com/miniupnp/miniupnp/tar.gz/refs/tags/miniupnpc_2_3_3 miniupnp-miniupnpc_2_3_3
fetch ffmpeg "https://github.com/FFmpeg/FFmpeg/archive/refs/tags/n$FFMPEG_VERSION.tar.gz" "FFmpeg-n$FFMPEG_VERSION"

if [[ ! -f "$PREFIX/lib/libcrypto.a" ]]; then
  echo "=== OpenSSL"
  mkdir -p "$WORK/openssl" && cd "$WORK/openssl"
  "$WORK/archives/openssl/Configure" "darwin64-$ARCH-cc" no-shared no-tests no-module no-async --prefix="$PREFIX" \
    --libdir=lib "-mmacosx-version-min=$MIN" >/dev/null
  make -s -j"$JOBS" build_libs >/dev/null && make -s install_dev >/dev/null
  cd "$NATIVE"
fi

common=(-G Ninja -DCMAKE_BUILD_TYPE=Release -DCMAKE_OSX_SYSROOT="$SYSROOT" -DCMAKE_OSX_ARCHITECTURES=$ARCH
        -DCMAKE_OSX_DEPLOYMENT_TARGET=$MIN -DCMAKE_INSTALL_PREFIX="$PREFIX" -DCMAKE_PREFIX_PATH="$PREFIX"
        -DCMAKE_IGNORE_PREFIX_PATH="/opt/homebrew;/usr/local" -DCMAKE_POLICY_VERSION_MINIMUM=3.5 -DBUILD_SHARED_LIBS=OFF)
dep() {
  local name=$1 src=$2; shift 2
  [[ -f "$WORK/.done-$name" ]] && return
  echo "=== $name"
  cmake -S "$src" -B "$WORK/build-$name" "${common[@]}" "$@" >/dev/null
  cmake --build "$WORK/build-$name" --target install --parallel "$JOBS" >/dev/null
  touch "$WORK/.done-$name"
}
dep json-c "$WORK/archives/json-c" -DBUILD_TESTING=OFF -DBUILD_APPS=OFF -DDISABLE_EXTRA_LIBS=ON -DBUILD_STATIC_LIBS=ON
# pipe2 SDK'da görünür ama yalnız yeni macOS'ta var; pipe() kullandırılır (CouchSubs'ta macOS 27'de görüldü).
dep libevent "$WORK/archives/libevent" -DEVENT__LIBRARY_TYPE=STATIC -DEVENT__DISABLE_OPENSSL=ON -DEVENT__DISABLE_MBEDTLS=ON \
  -DEVENT__DISABLE_TESTS=ON -DEVENT__DISABLE_SAMPLES=ON -DEVENT__DISABLE_BENCHMARK=ON -DEVENT__DISABLE_REGRESS=ON \
  -DEVENT__HAVE_PIPE2=0
dep miniupnpc "$WORK/archives/miniupnp/miniupnpc" -DUPNPC_BUILD_STATIC=ON -DUPNPC_BUILD_SHARED=OFF \
  -DUPNPC_BUILD_TESTS=OFF -DUPNPC_BUILD_SAMPLE=OFF

if [[ ! -f "$PREFIX/lib/libavcodec.a" ]]; then
  echo "=== FFmpeg (yalnız h264 çözücü + swscale)"
  mkdir -p "$WORK/ffmpeg" && cd "$WORK/ffmpeg"
  "$WORK/archives/ffmpeg/configure" --prefix="$PREFIX" --arch=$ARCH --target-os=darwin --cc=clang \
    --extra-cflags="-mmacosx-version-min=$MIN" --extra-ldflags="-mmacosx-version-min=$MIN" \
    --enable-static --disable-shared --disable-debug --disable-everything --disable-autodetect --enable-pthreads \
    --disable-programs --disable-doc --disable-network --disable-avdevice --disable-avformat --disable-avfilter \
    --disable-swresample --enable-avcodec --enable-avutil --enable-swscale --enable-decoder=h264 --enable-parser=h264 \
    >/dev/null
  make -s -j"$JOBS" >/dev/null && make -s install >/dev/null
  cd "$NATIVE"
fi

# protoc yalnız derleme aracı (bağlanmaz); Homebrew'dakini kullan. CMAKE_IGNORE_PREFIX_PATH onu gizlediği için yolu verilir.
PROTOC_BIN="$(command -v protoc || true)"
[[ -n "$PROTOC_BIN" ]] || { echo "HATA: protoc yok (brew install protobuf)" >&2; exit 1; }

echo "=== couchsubs_native"
export PKG_CONFIG_LIBDIR="$PREFIX/lib/pkgconfig"
export PKG_CONFIG_PATH=""
cmake -S "$NATIVE" -B "$WORK/native" "${common[@]}" -DFFMPEG_PREFIX="$PREFIX" \
  -DOPENSSL_ROOT_DIR="$PREFIX" -DOPENSSL_USE_STATIC_LIBS=ON -DCURL_USE_OPENSSL=ON \
  -DPython3_EXECUTABLE="$VENV/bin/python3" -DPYTHON_EXECUTABLE="$VENV/bin/python3" -DPROTOC="$PROTOC_BIN" >/dev/null
cmake --build "$WORK/native" --parallel "$JOBS"
"$WORK/native/couchsubs_native_test" "$NATIVE/fixtures/sample-1080p.h264"
cp "$WORK/native/couchsubs_native.dylib" "$NATIVE/bin/"

# Yalnız sistem kütüphanelerine bağlı olmalı ve macOS 13'ten yenisini istememeli.
DYLIB="$NATIVE/bin/couchsubs_native.dylib"
otool -L "$DYLIB"
bad=$(otool -L "$DYLIB" | tail -n +2 | awk '{print $1}' | grep -v 'couchsubs_native.dylib$' \
  | grep -Ev '^(/usr/lib/|/System/Library/)' || true)
[[ -z "$bad" ]] || { echo "HATA: sistem dışı bağımlılık: $bad" >&2; exit 1; }
minos=$(otool -l "$DYLIB" | awk '/minos/ {print $2}' | sort -uV | tail -1)
[[ "$(printf '%s\n%s\n' "$minos" "$MIN" | sort -V | tail -1)" == "$MIN" ]] || { echo "HATA: macOS $minos hedefleniyor" >&2; exit 1; }
# (grep -q borunun öbür ucunu erken kapatır; pipefail ile nm "Broken pipe" hatası sayılıyordu: önce değişkene al)
EXPORTS="$(nm -gU "$DYLIB")"
UNDEF="$(nm -u "$DYLIB")"
for fn in cs_init cs_discover_ex cs_wake cs_register cs_session_start_ex cs_session_stop; do
  grep -q " _$fn$" <<<"$EXPORTS" || { echo "HATA: dışa aktarılmamış: $fn" >&2; exit 1; }
done
if grep -qx "_pipe2" <<<"$UNDEF"; then echo "HATA: pipe2 kullanılıyor" >&2; exit 1; fi
ls -l "$DYLIB"
