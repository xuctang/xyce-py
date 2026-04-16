#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'EOF'
Usage:
  tools/cleanroom/run_registry_smoke.sh --index pypi|testpypi --version X.Y.Z --install-mode wheel|sdist|upgrade [--previous-version X.Y.Z]

The smoke install always comes from the selected package index. It never installs the local xyce-py checkout.
EOF
}

index_name=""
version=""
install_mode=""
previous_version=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --index)
      index_name="$2"
      shift 2
      ;;
    --version)
      version="$2"
      shift 2
      ;;
    --install-mode)
      install_mode="$2"
      shift 2
      ;;
    --previous-version)
      previous_version="$2"
      shift 2
      ;;
    --help|-h)
      usage
      exit 0
      ;;
    *)
      echo "Unknown argument: $1" >&2
      usage >&2
      exit 2
      ;;
  esac
done

if [[ -z "$index_name" || -z "$version" || -z "$install_mode" ]]; then
  echo "--index, --version, and --install-mode are required." >&2
  usage >&2
  exit 2
fi

case "$index_name" in
  pypi|testpypi)
    ;;
  *)
    echo "Unsupported --index value: $index_name" >&2
    exit 2
    ;;
esac

case "$install_mode" in
  wheel|sdist)
    ;;
  upgrade)
    if [[ -z "$previous_version" ]]; then
      echo "--previous-version is required when --install-mode upgrade is used." >&2
      exit 2
    fi
    ;;
  *)
    echo "Unsupported --install-mode value: $install_mode" >&2
    exit 2
    ;;
esac

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
repo_root="$(cd "$script_dir/../.." && pwd)"
image_name="xyce-py-cleanroom-smoke"

docker build -f "$script_dir/Dockerfile" -t "$image_name" "$repo_root"

docker run \
  --rm \
  -e INDEX_NAME="$index_name" \
  -e TARGET_VERSION="$version" \
  -e INSTALL_MODE="$install_mode" \
  -e PREVIOUS_VERSION="$previous_version" \
  "$image_name" \
  /bin/bash -lc '
    set -euo pipefail
    python -m pip install --upgrade pip

    case "$INDEX_NAME" in
      pypi)
        index_args=(--index-url https://pypi.org/simple)
        ;;
      testpypi)
        index_args=(--index-url https://test.pypi.org/simple/ --extra-index-url https://pypi.org/simple)
        ;;
      *)
        echo "Unsupported index: $INDEX_NAME" >&2
        exit 2
        ;;
    esac

    case "$INSTALL_MODE" in
      wheel)
        python -m pip install "${index_args[@]}" "xyce-py==$TARGET_VERSION"
        python /opt/xyce-py/release_smoke.py --expect-version "$TARGET_VERSION"
        ;;
      sdist)
        python -m pip install "${index_args[@]}" --no-binary xyce-py "xyce-py==$TARGET_VERSION"
        python /opt/xyce-py/release_smoke.py --expect-version "$TARGET_VERSION"
        ;;
      upgrade)
        python -m pip install "${index_args[@]}" "xyce-py==$PREVIOUS_VERSION"
        python /opt/xyce-py/release_smoke.py --expect-version "$PREVIOUS_VERSION"
        python -m pip install --upgrade --no-cache-dir "${index_args[@]}" "xyce-py==$TARGET_VERSION"
        python /opt/xyce-py/release_smoke.py --expect-version "$TARGET_VERSION"
        ;;
      *)
        echo "Unsupported install mode: $INSTALL_MODE" >&2
        exit 2
        ;;
    esac
  '
