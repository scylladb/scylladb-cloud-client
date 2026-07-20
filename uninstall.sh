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

remove_symlink_if_present() {
  _path=$1
  _missing_message=$2

  if [ -L "${_path}" ]; then
      rm "${_path}"
      echo "Removed ${_path}"
  elif [ -e "${_path}" ]; then
      echo "Leaving ${_path}: path exists but is not a symlink" >&2
  else
      echo "${_missing_message}"
  fi
}

echo "Uninstalling scylladb-cloud-client from ${PREFIX}"

assert_owned_by_effective_user_if_exists "$BIN_LINK"
assert_owned_by_effective_user_if_exists "$BIN_ALIAS"
assert_owned_by_effective_user_if_exists "$VENV_DIR"

remove_symlink_if_present "${BIN_ALIAS}" "No CLI alias symlink found at ${BIN_ALIAS}"
remove_symlink_if_present "${BIN_LINK}" "No CLI symlink found at ${BIN_LINK}"

if [ -d "${VENV_DIR}" ]; then
    rm -rf "${VENV_DIR}"
    echo "Removed ${VENV_DIR}"
elif [ -e "${VENV_DIR}" ]; then
    echo "Leaving ${VENV_DIR}: path exists but is not a directory" >&2
else
    echo "No private virtualenv found at ${VENV_DIR}"
fi

echo "Uninstalled scylladb-cloud-client."
