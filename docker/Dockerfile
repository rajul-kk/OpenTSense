# OpenTSense tool image: Icarus, Verilator, ngspice, 3D-ICE 4.0, PACT, HotSpot 7 and the Python stack.
# OpenROAD/OpenSTA/Yosys run from the pinned ORFS image instead (see versions.env).
# Build from the repo root:  scripts/build_image.sh
ARG UBUNTU_IMAGE=ubuntu:26.04
ARG OSDI_UBUNTU_IMAGE=ubuntu:24.04

# SPICE device models. OpenVAF-Reloaded needs LLVM 18, so it runs in a separate stage and only its output is kept.
FROM ${OSDI_UBUNTU_IMAGE} AS osdi
ARG APT_SNAPSHOT
ARG OPENVAF_VERSION
ARG OPENVAF_SHA256
ARG IHP_PDK_COMMIT
ARG VA_MODELS_COMMIT
ARG ASAP7_CELLS_COMMIT
RUN apt-get update -qq && apt-get install -y -qq --no-install-recommends ca-certificates && \
    apt-get update --snapshot "${APT_SNAPSHOT}" -qq && \
    apt-get install --snapshot "${APT_SNAPSHOT}" -y -qq --no-install-recommends curl git gcc libc6-dev libllvm18 && \
    curl -fsSL -o /tmp/ovaf.tgz "https://github.com/OpenVAF/OpenVAF-Reloaded/releases/download/${OPENVAF_VERSION}/openvaf-r-${OPENVAF_VERSION}-linux-x86_64.tar.gz" && \
    echo "${OPENVAF_SHA256}  /tmp/ovaf.tgz" | sha256sum -c - && mkdir /opt/ovaf && tar -xzf /tmp/ovaf.tgz -C /opt/ovaf --strip-components=1
RUN mkdir -p /spice/osdi /spice/ihp /spice/asap7/cdl /spice/licenses && \
    git clone -q --filter=blob:none --sparse --no-checkout https://github.com/IHP-GmbH/IHP-Open-PDK.git /src/ihp && cd /src/ihp && \
    git sparse-checkout set ihp-sg13g2/libs.tech/verilog-a ihp-sg13g2/libs.tech/ngspice/models ihp-sg13g2/libs.ref/sg13g2_stdcell/spice && \
    git checkout -q "${IHP_PDK_COMMIT}" && V=/src/ihp/ihp-sg13g2/libs.tech/verilog-a && \
    for f in psp103/psp103 psp103/psp103_nqs r3_cmc/r3_cmc mosvar/mosvar; do \
        ( cd "$V/$(dirname $f)" && /opt/ovaf/bin/openvaf-r -o "/spice/osdi/$(basename $f).osdi" "$(basename $f).va" ) || exit 1; done && \
    cp -r ihp-sg13g2/libs.tech/ngspice/models /spice/ihp/models && cp ihp-sg13g2/libs.ref/sg13g2_stdcell/spice/sg13g2_stdcell.spice /spice/ihp/ && \
    cp LICENSE /spice/licenses/IHP-Open-PDK.LICENSE && cp $V/r3_cmc/LICENSE.txt /spice/licenses/r3_cmc.LICENSE && sed -n 1,22p $V/psp103/psp103.va > /spice/licenses/psp103.NOTICE
RUN git clone -q --filter=blob:none --sparse --no-checkout https://github.com/dwarning/VA-Models.git /src/va && cd /src/va && \
    git sparse-checkout set code/bsimcmg/vacode110 && git checkout -q "${VA_MODELS_COMMIT}" && cd code/bsimcmg/vacode110 && \
    /opt/ovaf/bin/openvaf-r -o /spice/osdi/bsimcmg.osdi bsimcmg.va && sed -n 1,45p bsimcmg.va > /spice/licenses/bsimcmg.NOTICE
RUN git clone -q --filter=blob:none --sparse --no-checkout https://github.com/The-OpenROAD-Project/asap7sc7p5t_28.git /src/a7 && cd /src/a7 && \
    git sparse-checkout set CDL/LVS && git checkout -q "${ASAP7_CELLS_COMMIT}" && cp CDL/LVS/asap7sc7p5t_28_*.cdl /spice/asap7/cdl/ && cp LICENSE /spice/licenses/asap7.LICENSE && \
    printf 'openvaf-r %s\nIHP-Open-PDK %s\nVA-Models %s\nasap7sc7p5t_28 %s\n' "${OPENVAF_VERSION}" "${IHP_PDK_COMMIT}" "${VA_MODELS_COMMIT}" "${ASAP7_CELLS_COMMIT}" > /spice/VERSIONS

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
# SuperLU_MT allocates its L and U storage once, as a multiple of nnz(A) set in sp_ienv.c, and can't grow it. The
# default (50x, 30x for L subscripts) is too small for finely layered stacks (G71), so it is raised to 400x / 250x.
# Linux only commits pages that are touched, so small problems use no more memory than before.
COPY docker/patches/3d-ice-4953952.patch docker/patches/superlu_mt-4.0.0.make.inc /tmp/
RUN git clone -q https://github.com/esl-epfl/3d-ice.git /opt/3d-ice && cd /opt/3d-ice && \
    git checkout -q "${ICE_COMMIT}" && patch -p1 < /tmp/3d-ice-4953952.patch && \
    git clone -q https://github.com/xiaoyeli/superlu_mt.git superlu_mt-4.0.0 && \
    git -C superlu_mt-4.0.0 checkout -q "${SLU_COMMIT}" && cp /tmp/superlu_mt-4.0.0.make.inc superlu_mt-4.0.0/make.inc && mkdir -p superlu_mt-4.0.0/lib && \
    sed -i 's/case 6: return (-50);/case 6: return (-400);/; s/case 7: return (-50);/case 7: return (-400);/; s/case 8: return (-30);/case 8: return (-250);/' superlu_mt-4.0.0/SRC/sp_ienv.c && \
    grep -q 'case 7: return (-400);' superlu_mt-4.0.0/SRC/sp_ienv.c && \
    { make -C superlu_mt-4.0.0 superlulib > /tmp/slu.log 2>&1 || { tail -40 /tmp/slu.log; exit 1; }; } && \
    { make -j"$(nproc)" > /tmp/ice.log 2>&1 || { tail -60 /tmp/ice.log; exit 1; }; } && \
    git rev-parse HEAD > COMMIT && test -x bin/3D-ICE-Emulator
ENV PATH=/opt/3d-ice/bin:$PATH

# PACT at a fixed commit, with numpy/pandas 2 compatibility fixes
COPY docker/patches/pact-bb7f05a.patch /tmp/
RUN git clone -q https://github.com/peaclab/PACT.git /opt/pact && cd /opt/pact && \
    git checkout -q "${PACT_COMMIT}" && patch -p1 < /tmp/pact-bb7f05a.patch && git rev-parse HEAD > COMMIT
ENV PACT_SRC=/opt/pact/src
# G93a: any material label with a stack-config section is an isotropic solid (PACT accepts only a fixed list)
COPY docker/patches/pact-labels.patch /tmp/
RUN cd /opt/pact && patch -p1 < /tmp/pact-labels.patch && grep -q "OpenTSense: any other label" src/GridManager.py

# G93a: HotSpot 7 (grid model, SuperLU direct solver) at a fixed commit, as the third thermal solver. Its licence
# (BSD-style, University of Virginia) requires the notice in every copy, binary included: it is kept in /opt/hotspot.
# Patch: the steady grid dump prints 6 decimals instead of 2 (output format only).
ARG HOTSPOT_COMMIT
COPY docker/patches/hotspot-f18831e.patch /tmp/
RUN apt-get update --snapshot "${APT_SNAPSHOT}" -qq && \
    apt-get install --snapshot "${APT_SNAPSHOT}" -y -qq --no-install-recommends libsuperlu-dev libblas-dev && \
    rm -rf /var/lib/apt/lists/* && \
    git clone -q https://github.com/uvahotspot/HotSpot.git /opt/hotspot && cd /opt/hotspot && \
    git checkout -q "${HOTSPOT_COMMIT}" && patch -p1 < /tmp/hotspot-f18831e.patch && \
    { make SUPERLU=1 hotspot > /tmp/hs.log 2>&1 || { tail -40 /tmp/hs.log; exit 1; }; } && \
    git rev-parse HEAD > COMMIT && test -x hotspot && test -s LICENSE
ENV PATH=/opt/hotspot:$PATH

# Python stack, exact pins
COPY docker/requirements.lock /tmp/
RUN python3 -m venv /opt/venv && /opt/venv/bin/pip install -q --no-cache-dir -r /tmp/requirements.lock
ENV PATH=/opt/venv/bin:$PATH

# SPICE models from the osdi stage. ngspice loads the .osdi plugins itself; opentsense/power/leak.py writes the decks.
COPY --from=osdi /spice /opt/spice
COPY docker/models/7nm_TT.pm docker/asap7_osdi.py /tmp/
RUN python3 /tmp/asap7_osdi.py /tmp/7nm_TT.pm /opt/spice/asap7/cdl /opt/spice/asap7 && \
    for f in psp103 psp103_nqs r3_cmc mosvar bsimcmg; do test -s "/opt/spice/osdi/$f.osdi"; done && \
    sha256sum /opt/spice/osdi/*.osdi /opt/spice/asap7/*.* /opt/spice/ihp/models/cornerMOSlv.lib | sha256sum | cut -d' ' -f1 > /opt/spice/CHECKSUM
ENV SPICE_ROOT=/opt/spice

RUN git config --system --add safe.directory "*"
WORKDIR /work
