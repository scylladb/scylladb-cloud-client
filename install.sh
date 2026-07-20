#!/usr/bin/env sh
set -eu

PREFIX="${1:-${PREFIX:-/usr/local}}"
PYTHON="${PYTHON:-python3}"

SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
VENV_DIR="${PREFIX}/lib/scylladb-cloud-client"
BIN_DIR="${PREFIX}/bin"
BIN_LINK="${BIN_DIR}/scylladb-cloud-client"
BIN_ALIAS="${BIN_DIR}/scc"

die() {
  echo "install.sh: $*" >&2
  exit 1
}

is_root() {
  [ "$(id -u)" -eq 0 ]
}

# Refuse to modify paths that exist but belong to another user (unless root).
assert_owned_by_effective_user_if_exists() {
  _path=$1
  [ ! -e "$_path" ] && return 0
  if ! is_root && [ ! -O "$_path" ]; then
    die "refusing to touch ${_path}: not owned by the current user (use your own prefix, e.g. \$HOME/.local, or run as root for system-wide installs)."
  fi
}

# Ensure we can create _target under its ancestors (non-root only).
assert_parent_writable_owned_for_target() {
  _target=$1
  is_root && return 0
  _dir=$(dirname "$_target")
  while [ ! -d "$_dir" ]; do
    _parent=$(dirname "$_dir")
    [ "$_parent" = "$_dir" ] && break
    _dir=$_parent
  done
  [ -d "$_dir" ] || die "parent directory for ${_target} does not exist (${_dir}); create it or choose a different PREFIX."
  if [ ! -O "$_dir" ] || [ ! -w "$_dir" ]; then
    die "refusing to create ${_target}: ${_dir} is not writable or not owned by you."
  fi
}

echo "Installing scylladb-cloud-client to ${PREFIX}"

assert_owned_by_effective_user_if_exists "$PREFIX"
assert_owned_by_effective_user_if_exists "${PREFIX}/lib"
assert_owned_by_effective_user_if_exists "$VENV_DIR"
assert_owned_by_effective_user_if_exists "$BIN_DIR"
assert_owned_by_effective_user_if_exists "$BIN_LINK"
assert_owned_by_effective_user_if_exists "$BIN_ALIAS"
assert_parent_writable_owned_for_target "$VENV_DIR"
assert_parent_writable_owned_for_target "$BIN_LINK"
assert_parent_writable_owned_for_target "$BIN_ALIAS"

"${PYTHON}" -m venv "${VENV_DIR}"
"${VENV_DIR}/bin/python" -m pip install --upgrade "${SCRIPT_DIR}"
mkdir -p "${BIN_DIR}"
ln -sf "${VENV_DIR}/bin/scylladb-cloud-client" "${BIN_LINK}"
ln -sf "${BIN_LINK}" "${BIN_ALIAS}"

cat <<EOF

Installed scylladb-cloud-client.
If the command is not on your PATH, add:
  ${BIN_DIR}
EOF
