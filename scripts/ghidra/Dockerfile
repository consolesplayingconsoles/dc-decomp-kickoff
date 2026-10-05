# Headless Ghidra for SH-4 analysis on any host with Docker. The decompiler binary Ghidra ships is
# linux_x86_64 / win_x86_64 only, so this image is amd64 (emulated on Apple Silicon: slower, works).
#   docker build --platform linux/amd64 -t dc-ghidra scripts/ghidra
FROM --platform=linux/amd64 eclipse-temurin:21-jdk
ARG GHIDRA_URL=https://github.com/NationalSecurityAgency/ghidra/releases/download/Ghidra_12.1.4_build/ghidra_12.1.4_PUBLIC_20260921.zip
ARG GHIDRA_SHA256=ddac49f903da9d5bac833e5cc79395098b9c33cfd3279be5f31bd00387d2d4db
RUN apt-get update && apt-get install -y --no-install-recommends unzip curl && rm -rf /var/lib/apt/lists/* \
 && curl -fsSL -o /tmp/ghidra.zip "$GHIDRA_URL" \
 && echo "$GHIDRA_SHA256  /tmp/ghidra.zip" | sha256sum -c - \
 && unzip -q /tmp/ghidra.zip -d /opt && rm /tmp/ghidra.zip \
 && ln -s /opt/ghidra_* /opt/ghidra
COPY *.java /scripts/
ENV GHIDRA_INSTALL_DIR=/opt/ghidra
WORKDIR /work
ENTRYPOINT ["/opt/ghidra/support/analyzeHeadless"]
