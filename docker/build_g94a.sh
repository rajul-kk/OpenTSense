#!/bin/bash
# Build opentsense:g94a (HotSpot patch amendment 2 on top of g93a); log in docker/build_g94a.log
cd "$(dirname "$0")/.."
docker build -f docker/Dockerfile.g94a -t opentsense:g94a docker > docker/build_g94a.log 2>&1
echo "EXIT=$?" >> docker/build_g94a.log
