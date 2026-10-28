# Ephemeral sandbox image for agent code execution.
#
# Image-level hardening: non-root user, byte-code writing disabled,
# headless matplotlib. The run-level hardening (no network, read-only
# rootfs, memory/CPU caps) is applied by packages/sandbox/manager.py.
FROM python:3.12-slim

# Non-root user - the container process runs as this account, so the
# generated code can't touch system directories even before --read-only.
RUN useradd --create-home --uid 1000 sandbox

# Data + plotting libraries available to generated code
RUN pip install --no-cache-dir "pandas>=2.0" "numpy>=1.26" "matplotlib>=3.8"

# Writable caches go under /tmp (mounted tmpfs at run time), never the rootfs
ENV PYTHONDONTWRITEBYTECODE=1 \
    MPLBACKEND=Agg \
    MPLCONFIGDIR=/tmp/matplotlib \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app
USER sandbox

CMD ["python"]
