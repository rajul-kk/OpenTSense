#!/bin/bash
# Build opentsense:g93a (G93a: PACT label patch + HotSpot 7) detached; log in docker/build_g93a.log
cd "$(dirname "$0")/.."
scripts/build_image.sh opentsense:g93a > docker/build_g93a.log 2>&1
echo "EXIT=$?" >> docker/build_g93a.log
