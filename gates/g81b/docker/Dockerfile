# G81b compiler image: Ubuntu 24.04's RISC-V bare-metal GCC + picolibc, from a pinned apt snapshot.
ARG UBUNTU=ubuntu:24.04@sha256:fe81560990fae86dc4743202b2cb4d3df98d0bcf949173cecef15ce1127ef852
FROM ${UBUNTU}
ARG APT_SNAPSHOT=20261031T000000Z
RUN apt-get update -qq && apt-get install -y -qq --no-install-recommends ca-certificates \
 && apt-get update -qq --snapshot ${APT_SNAPSHOT} \
 && DEBIAN_FRONTEND=noninteractive apt-get install -y -qq --no-install-recommends --snapshot ${APT_SNAPSHOT} \
      gcc-riscv64-unknown-elf picolibc-riscv64-unknown-elf binutils-riscv64-unknown-elf python3 make \
 && rm -rf /var/lib/apt/lists/* \
 && riscv64-unknown-elf-gcc --version | head -1 > /compiler_version.txt \
 && dpkg-query -W gcc-riscv64-unknown-elf picolibc-riscv64-unknown-elf binutils-riscv64-unknown-elf >> /compiler_version.txt
