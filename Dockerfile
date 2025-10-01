FROM python:3.12-slim

# Install system dependencies: TeX Live (xelatex) and tools
RUN apt-get update && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
    curl ca-certificates gnupg unzip \
    texlive-xetex texlive-latex-recommended texlive-latex-extra texlive-fonts-recommended \
    fonts-noto fonts-noto-cjk fonts-noto-color-emoji \
 && rm -rf /var/lib/apt/lists/*

# Install cloudflared (official Debian repo provides a static binary via GitHub as well)
RUN curl -L https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64 -o /usr/local/bin/cloudflared \
 && chmod +x /usr/local/bin/cloudflared

# Install uv for fast Python dependency management
RUN pip install --no-cache-dir uv

WORKDIR /app

# Copy project files
COPY pyproject.toml uv.lock* ./
RUN uv venv && . .venv/bin/activate && uv sync --frozen

COPY . .

# Ensure dependencies are in sync with the complete source (cache-friendly second pass)
RUN . .venv/bin/activate && uv sync --frozen

# Ensure entrypoint is executable
RUN chmod +x /app/entrypoint.sh || true

# Expose MCP HTTP port
EXPOSE 8000

ENV PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    UV_SYSTEM_PYTHON=0 \
    PATH="/app/.venv/bin:${PATH}"

ENTRYPOINT ["/app/entrypoint.sh"]

