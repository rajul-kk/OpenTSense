#!/bin/bash
# Build the OpenTSense tool image from docker/versions.env. Usage: scripts/build_image.sh [tag] [--no-cache]
set -euo pipefail
cd "$(dirname "$0")/.."
set -a; . docker/versions.env; set +a
TAG=${1:-opentsense:dev}; shift || true
docker build "$@" -f docker/Dockerfile -t "$TAG" \
  --build-arg UBUNTU_IMAGE="$UBUNTU_IMAGE" --build-arg APT_SNAPSHOT="$APT_SNAPSHOT" \
  --build-arg ICE_COMMIT="$ICE_COMMIT" --build-arg SLU_COMMIT="$SLU_COMMIT" --build-arg PACT_COMMIT="$PACT_COMMIT" \
  --build-arg OSDI_UBUNTU_IMAGE="$OSDI_UBUNTU_IMAGE" --build-arg OPENVAF_VERSION="$OPENVAF_VERSION" --build-arg OPENVAF_SHA256="$OPENVAF_SHA256" \
  --build-arg IHP_PDK_COMMIT="$IHP_PDK_COMMIT" --build-arg VA_MODELS_COMMIT="$VA_MODELS_COMMIT" --build-arg ASAP7_CELLS_COMMIT="$ASAP7_CELLS_COMMIT" .
docker image inspect "$TAG" --format '{{.Id}}'
