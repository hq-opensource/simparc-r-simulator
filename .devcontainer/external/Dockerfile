# Dockerfile for VS Code Dev Container
FROM nrel/openstudio:3.9.0

# Install Python and set python3 as default
RUN apt-get update && \
    apt-get install -y --no-install-recommends ca-certificates python3 python3-pip python3-venv && \
    update-alternatives --install /usr/bin/python python /usr/bin/python3 1 && \
    rm -rf /var/lib/apt/lists/*

# Install UV package manager
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# Set working directory
WORKDIR /workspace

# Set container flag
ENV AM_I_IN_A_DOCKER_CONTAINER=Yes
