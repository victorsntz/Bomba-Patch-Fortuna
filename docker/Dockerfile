# Ambiente do Bomba Patch Fortuna para quem não está num Linux x86-64.
# O ./fortuna monta e usa esta imagem sozinho; não precisa rodar nada aqui na mão.
# As versões batem com o UPSTREAM.lock. Mudou lá, muda aqui.

FROM ubuntu:24.04 AS base
ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update \
 && apt-get install -y --no-install-recommends ca-certificates curl git unzip xz-utils python3 cmake ninja-build clang p7zip-full \
 && rm -rf /var/lib/apt/lists/*
ARG EMSDK_VERSION=6.0.11
RUN git clone --depth 1 https://github.com/emscripten-core/emsdk.git /opt/emsdk \
 && /opt/emsdk/emsdk install ${EMSDK_VERSION} \
 && /opt/emsdk/emsdk activate ${EMSDK_VERSION} \
 && rm -rf /opt/emsdk/downloads
ENV EMSDK=/opt/emsdk
# a pasta do kit é montada de fora e pertence ao seu usuário, não ao do contêiner
RUN git config --system --add safe.directory '*'

# para o ./fortuna investigar e o ./fortuna rea: Java, Ghidra e o REA
FROM base AS investigacao
RUN apt-get update \
 && apt-get install -y --no-install-recommends openjdk-21-jdk-headless \
 && rm -rf /var/lib/apt/lists/*
ARG GHIDRA_ZIP=https://github.com/NationalSecurityAgency/ghidra/releases/download/Ghidra_12.1.3_build/ghidra_12.1.3_PUBLIC_20260817.zip
RUN curl -L --fail -o /tmp/ghidra.zip "${GHIDRA_ZIP}" \
 && unzip -q /tmp/ghidra.zip -d /opt \
 && rm /tmp/ghidra.zip \
 && ln -s /opt/ghidra_*_PUBLIC /opt/ghidra
ENV GHIDRA_INSTALL_DIR=/opt/ghidra
# o Emscripten já traz um Node 24, que serve para o REA
ARG REA_VERSION=6.4.0
RUN ln -s "$(ls -d /opt/emsdk/node/*/bin | head -1)" /opt/node-bin \
 && PATH=/opt/node-bin:$PATH npm install -g "rea-agents@${REA_VERSION}"
ENV PATH=/opt/node-bin:$PATH
