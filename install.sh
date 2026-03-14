#!/usr/bin/env bash
set -euo pipefail

REPO="tappress/qualify"   # TODO: update before release
BIN_DIR="${HOME}/.local/bin"
BINARY="${BIN_DIR}/qualify"

info() { printf "\033[1;34m→\033[0m %s\n" "$*"; }
ok()   { printf "\033[1;32m✓\033[0m %s\n" "$*"; }
err()  { printf "\033[1;31m✗\033[0m %s\n" "$*" >&2; exit 1; }

command -v curl &>/dev/null || err "curl is required"

# Detect OS + arch
OS=$(uname -s)
ARCH=$(uname -m)

case "${OS}-${ARCH}" in
  Linux-x86_64)   ASSET="qualify-linux-x86_64" ;;
  Darwin-arm64)   ASSET="qualify-macos-arm64" ;;
  Darwin-x86_64)  ASSET="qualify-macos-x86_64" ;;
  *)              err "Unsupported platform: ${OS}-${ARCH}. Use Windows installer or build from source." ;;
esac

mkdir -p "${BIN_DIR}"

# Resolve source: explicit path > local dist/ build > GitHub release
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LOCAL_BUILD="${SCRIPT_DIR}/dist/qualify"

if [[ -n "${QUALIFY_BIN_PATH:-}" ]]; then
  [[ -f "${QUALIFY_BIN_PATH}" ]] || err "File not found: ${QUALIFY_BIN_PATH}"
  info "Installing from explicit path: ${QUALIFY_BIN_PATH}"
  cp "${QUALIFY_BIN_PATH}" "${BINARY}"
elif [[ -f "${LOCAL_BUILD}" ]]; then
  info "Found local build at dist/qualify — installing that"
  cp "${LOCAL_BUILD}" "${BINARY}"
else
  # No local binary — fetch from GitHub
  if [[ -n "${VERSION:-}" ]]; then
    TAG="${VERSION}"
  else
    info "Fetching latest release..."
    TAG=$(curl -fsSL "https://api.github.com/repos/${REPO}/releases/latest" \
      | grep '"tag_name"' | head -1 | cut -d'"' -f4)
    [[ -z "${TAG}" ]] && err "Could not determine latest release. Set VERSION=vX.Y.Z to override."
  fi
  info "Installing Qualify ${TAG} (${ASSET})..."
  curl -fsSL "https://github.com/${REPO}/releases/download/${TAG}/${ASSET}" -o "${BINARY}"
fi

chmod +x "${BINARY}"

ok "Installed to ${BINARY}"

if [[ ":${PATH}:" != *":${BIN_DIR}:"* ]]; then
  printf "\n\033[1;33m⚠\033[0m  Add to your shell profile:\n"
  printf "    export PATH=\"\$HOME/.local/bin:\$PATH\"\n\n"
else
  printf "\nRun \033[1mqualify\033[0m to start.\n"
fi
