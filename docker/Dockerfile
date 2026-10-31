# OpenTSense tool image: Icarus, Verilator, ngspice, 3D-ICE 4.0, PACT and the Python stack.
# OpenROAD/OpenSTA/Yosys run from the pinned ORFS image instead (see versions.env).
# Build from the repo root:  scripts/build_image.sh
ARG UBUNTU_IMAGE=ubuntu:26.04
FROM ${UBUNTU_IMAGE}

ARG APT_SNAPSHOT
ARG ICE_COMMIT
ARG SLU_COMMIT
ARG PACT_COMMIT
ENV DEBIAN_FRONTEND=noninteractive

# apt packages come from a dated Ubuntu snapshot, so a rebuild gets the same versions. The snapshot server is
# HTTPS-only and the base image has no CA certificates, so those come first from the live archive (transport only;
# packages are still checked against Ubuntu's signing keys). The manifest records the ca-certificates version.
RUN apt-get update -qq && apt-get install -y -qq --no-install-recommends ca-certificates && \
    apt-get update --snapshot "${APT_SNAPSHOT}" -qq && \
    apt-get install --snapshot "${APT_SNAPSHOT}" -y -qq --no-install-recommends \
        build-essential git ca-certificates unzip patch bison flex libopenblas-dev \
        iverilog verilator ngspice python3 python3-venv python3-dev && \
    rm -rf /var/lib/apt/lists/*

# 3D-ICE 4.0 at a fixed commit. SuperLU_MT comes from its own repo at a fixed commit (its prototype fixes are needed
# under GCC 15; the 4.0.0 zip shipped with 3D-ICE does not compile), built with the exploratory WSL make.inc
# (C99, OpenBLAS). It sits where 3D-ICE's makefile.def expects superlu_mt-4.0.0.
COPY docker/patches/3d-ice-4953952.patch docker/patches/superlu_mt-4.0.0.make.inc /tmp/
RUN git clone -q https://github.com/esl-epfl/3d-ice.git /opt/3d-ice && cd /opt/3d-ice && \
    git checkout -q "${ICE_COMMIT}" && patch -p1 < /tmp/3d-ice-4953952.patch && \
    git clone -q https://github.com/xiaoyeli/superlu_mt.git superlu_mt-4.0.0 && \
    git -C superlu_mt-4.0.0 checkout -q "${SLU_COMMIT}" && cp /tmp/superlu_mt-4.0.0.make.inc superlu_mt-4.0.0/make.inc && mkdir -p superlu_mt-4.0.0/lib && \
    { make -C superlu_mt-4.0.0 superlulib > /tmp/slu.log 2>&1 || { tail -40 /tmp/slu.log; exit 1; }; } && \
    { make -j"$(nproc)" > /tmp/ice.log 2>&1 || { tail -60 /tmp/ice.log; exit 1; }; } && \
    git rev-parse HEAD > COMMIT && test -x bin/3D-ICE-Emulator
ENV PATH=/opt/3d-ice/bin:$PATH

# PACT at a fixed commit, with numpy/pandas 2 compatibility fixes
COPY docker/patches/pact-bb7f05a.patch /tmp/
RUN git clone -q https://github.com/peaclab/PACT.git /opt/pact && cd /opt/pact && \
    git checkout -q "${PACT_COMMIT}" && patch -p1 < /tmp/pact-bb7f05a.patch && git rev-parse HEAD > COMMIT
ENV PACT_SRC=/opt/pact/src

# Python stack, exact pins
COPY docker/requirements.lock /tmp/
RUN python3 -m venv /opt/venv && /opt/venv/bin/pip install -q --no-cache-dir -r /tmp/requirements.lock
ENV PATH=/opt/venv/bin:$PATH

RUN git config --system --add safe.directory "*"
WORKDIR /work
