FROM node:22-bookworm-slim
RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates curl git python3-venv && rm -rf /var/lib/apt/lists/*
USER node
ENV HOME=/home/node
ENV PATH=/home/node/.local/bin:${PATH}
WORKDIR /home/node
