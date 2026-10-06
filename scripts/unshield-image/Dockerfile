# Older Katana SDK discs ship their files inside InstallShield cabinets (data1.hdr + data*.cab).
# unshield (Debian package) unpacks them on any OS through Docker, no Windows installer run.
#   docker build -t dc-unshield scripts/unshield-image
FROM debian:bookworm-slim
RUN apt-get update && apt-get install -y --no-install-recommends unshield \
 && rm -rf /var/lib/apt/lists/*
