#!/usr/bin/env bash
# Derlenen kurulum dosyasını GitHub'daki sürüm sayfasına (vX.Y.Z) koyar. Windows ve Mac işleri ortak kullanır.
#
#   bash tools/surum_yayinla.sh dist/GTA6Altyazi-Setup.exe
#
# Sürüm sayfası yoksa açılır. 0.9.6'da GitHub'ın iş anahtarı (GITHUB_TOKEN) yeni sürüm açarken "HTTP 403: Resource
# not accessible by integration" verdi. Bu yüzden üç yol sırayla denenir: (1) gh release create, (2) etiketi git ile
# itip var olan etikete sürüm açma, (3) öbür iş (Windows/Mac) aynı anda açmış olabilir diye bekleyip yeniden bakma.
# Hiçbiri olmazsa ne yapılacağı açıkça yazılır; kurulum dosyası işin "Artifacts" bölümüne de konur (iş dosyasında).
set -u
file="$1"
v=$(python -c "import altyazi; print(altyazi.__version__)")
tag="v$v"
sha="${GITHUB_SHA}"
title="GTA6 Altyazı $v"
python tools/surum_notu.py "$v" notlar.md "${sha:0:7}"

exists() { gh release view "$tag" >/dev/null 2>&1; }

for i in 1 2 3 4; do
  exists && break
  echo "Sürüm sayfası açılıyor: $tag (deneme $i)"
  gh release create "$tag" --target "$sha" --prerelease --title "$title" --notes-file notlar.md && break
  if ! git ls-remote --exit-code --tags origin "refs/tags/$tag" >/dev/null 2>&1; then
    echo "Etiket git ile gönderiliyor: $tag -> $sha"
    git tag -f "$tag" "$sha" && git push origin "refs/tags/$tag" || echo "Etiket gönderilemedi (yukarıdaki yazı sebebi söyler)"
  fi
  gh release create "$tag" --verify-tag --prerelease --title "$title" --notes-file notlar.md && break
  sleep 20
done

if ! exists; then
  echo "::error title=Sürüm sayfası açılamadı::GitHub $tag sayfasını açtırmadı. Çözüm: github.com/${GITHUB_REPOSITORY}/releases/new adresinde etiket olarak $tag yaz, hedef olarak bu commit'i ($sha) seç, 'Set as a pre-release' işaretle ve yayınla; sonra bu işi 'Re-run failed jobs' ile yeniden çalıştır. Kurulum dosyası bu çalışmanın Artifacts bölümünde de var."
  exit 1
fi
gh release edit "$tag" --notes-file notlar.md || true
gh release upload "$tag" "$file" --clobber
