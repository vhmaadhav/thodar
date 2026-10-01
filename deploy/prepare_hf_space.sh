#!/bin/sh
# Assembles a ready-to-push Hugging Face Space folder from the committed code. Does NOT deploy.
#
#   sh deploy/prepare_hf_space.sh            -> ./dist/hf-space
#
# Then, only when you decide to publish (needs a Space created as SDK "Docker"):
#   cd dist/hf-space && git init -b main && git add -A && git commit -m "Thodar demo" \
#     && git remote add space https://huggingface.co/spaces/<user>/<space> && git push space main
# Optional secret in the Space settings: THODAR_SARVAM_API_KEY (and THODAR_AI_DAILY_BUDGET to cap spend).
set -e
root=$(git rev-parse --show-toplevel)
out="$root/dist/hf-space"
rm -rf "$out"
mkdir -p "$out"
# Only committed files: no .env, no node_modules, no local databases.
git -C "$root" archive --format=tar HEAD Dockerfile .dockerignore backend frontend deploy | tar -x -C "$out"
cp "$root/deploy/hf-space/README.md" "$out/README.md"
if grep -rIl "sk_[A-Za-z0-9]\{8,\}" "$out" >/dev/null 2>&1; then
  echo "Refusing: something that looks like an API key is in the Space folder" >&2
  exit 1
fi
echo "Space folder ready: $out"
du -sh "$out" 2>/dev/null || true
