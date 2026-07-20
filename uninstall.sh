#!/usr/bin/env sh
set -eu

PREFIX="${1:-${PREFIX:-/usr/local}}"

VENV_DIR="${PREFIX}/lib/scylladb-cloud-client"
BIN_LINK="${PREFIX}/bin/scylladb-cloud-client"
BIN_ALIAS="${PREFIX}/bin/scc"

die() {
  echo "uninstall.sh: $*" >&2
  exit 1
}

is_root() {
  [ "$(id -u)" -eq 0 ]
}

assert_owned_by_effective_user_if_exists() {
  _path=$1
  [ ! -e "$_path" ] && return 0
  if ! is_root && [ ! -O "$_path" ]; then
    die "refusing to remove ${_path}: not owned by the current user (use sudo if this install was done as root)."
  fi
}

echo "Uninstalling scylladb-cloud-client from ${PREFIX}"

assert_owned_by_effective_user_if_exists "$BIN_LINK"
assert_owned_by_effective_user_if_exists "$BIN_ALIAS"
assert_owned_by_effective_user_if_exists "$VENV_DIR"

if [ -L "${BIN_ALIAS}" ]; then
    rm "${BIN_ALIAS}"
    echo "Removed ${BIN_ALIAS}"
elif [ -e "${BIN_ALIAS}" ]; then
    echo "Leaving ${BIN_ALIAS}: path exists but is not a symlink" >&2
else
    echo "No CLI alias symlink found at ${BIN_ALIAS}"
fi

if [ -L "${BIN_LINK}" ]; then
    rm "${BIN_LINK}"
    echo "Removed ${BIN_LINK}"
elif [ -e "${BIN_LINK}" ]; then
    echo "Leaving ${BIN_LINK}: path exists but is not a symlink" >&2
else
    echo "No CLI symlink found at ${BIN_LINK}"
fi

if [ -d "${VENV_DIR}" ]; then
    rm -rf "${VENV_DIR}"
    echo "Removed ${VENV_DIR}"
elif [ -e "${VENV_DIR}" ]; then
    echo "Leaving ${VENV_DIR}: path exists but is not a directory" >&2
else
    echo "No private virtualenv found at ${VENV_DIR}"
fi

echo "Uninstalled scylladb-cloud-client."
