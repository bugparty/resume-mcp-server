# Stage 1: Install TeX Live
FROM python:3.12-slim AS tex-installer

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    DEBIAN_FRONTEND=noninteractive

RUN apt-get update && apt-get install -y --no-install-recommends \
    wget \
    perl \
    xz-utils \
    && rm -rf /var/lib/apt/lists/*

# Configure TeX Live environment variables for installation
ENV TL_YEAR=2024
ENV TL_ROOT=/usr/local/texlive/${TL_YEAR}
ENV CTAN_MIRROR=https://ctan.math.utah.edu/ctan/tex-archive/

# Create TeX Live profile
WORKDIR /tmp/tlinst
RUN echo 'selected_scheme scheme-full' > texlive.profile && \
    echo "TEXDIR ${TL_ROOT}" >> texlive.profile && \
    echo 'TEXMFCONFIG ~/.texlive2024/texmf-config' >> texlive.profile && \
    echo 'TEXMFHOME ~/.texlive2024/texmf' >> texlive.profile && \
    echo 'TEXMFLOCAL /usr/local/texlive/texmf-local' >> texlive.profile && \
    echo "TEXMFSYSCONFIG ${TL_ROOT}/texmf-config" >> texlive.profile && \
    echo "TEXMFSYSVAR ${TL_ROOT}/texmf-var" >> texlive.profile && \
    echo 'TEXMFVAR ~/.texlive2024/texmf-var' >> texlive.profile && \
    echo 'binary_x86_64-linux 1' >> texlive.profile && \
    echo 'collection-langchinese 1' >> texlive.profile && \
    echo 'option_doc 0' >> texlive.profile && \
    echo 'option_src 0' >> texlive.profile && \
    echo 'option_autobackup 0' >> texlive.profile && \
    echo 'option_desktop_integration 0' >> texlive.profile && \
    echo 'option_file_assocs 0' >> texlive.profile

# Download and Install TeX Live
RUN wget --progress=dot:giga ${CTAN_MIRROR}/systems/texlive/tlnet/install-tl-unx.tar.gz && \
    tar -xzf install-tl-unx.tar.gz --strip-components=1 && \
    ./install-tl -profile texlive.profile -repository ${CTAN_MIRROR}/systems/texlive/tlnet

# Add to PATH for tlmgr
ENV PATH="${TL_ROOT}/bin/x86_64-linux:${PATH}"

# Install additional packages
RUN tlmgr option repository ${CTAN_MIRROR}/systems/texlive/tlnet && \
    tlmgr update --self --all && \
    tlmgr install \
        latexmk \
        fontawesome5 \
        enumitem \
        ragged2e \
        setspace \
        parskip \
        fancyhdr \
        xcolor \
        ifmtarg \
        xifthen \
        etoolbox \
        needspace \
        sourcesanspro \
        tcolorbox \
        environ \
        trimspaces xstring unicode-math fontawesome6 roboto tikzfill bookmark

# Stage 2: Python Dependencies
FROM python:3.12-slim AS venv-builder

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app
COPY requirements.txt .
RUN python -m venv /opt/venv && \
    /opt/venv/bin/pip install --no-cache-dir -U pip && \
    /opt/venv/bin/pip install --no-cache-dir -r requirements.txt

# Stage 3: Final Runtime
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    DEBIAN_FRONTEND=noninteractive \
    TL_YEAR=2024

# Runtime dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    ghostscript \
    fontconfig \
    fonts-droid-fallback \
    fonts-noto-cjk \
    perl \
    && rm -rf /var/lib/apt/lists/*

# Set TeX Live ENV
ENV TL_ROOT=/usr/local/texlive/${TL_YEAR}
ENV PATH="${TL_ROOT}/bin/x86_64-linux:/opt/venv/bin:${PATH}"
ENV MANPATH="${TL_ROOT}/texmf-dist/doc/man:${MANPATH}"
ENV INFOPATH="${TL_ROOT}/texmf-dist/doc/info:${INFOPATH}"

# Copy TeX Live from installer
COPY --from=tex-installer ${TL_ROOT} ${TL_ROOT}

# Copy Venv from builder
COPY --from=venv-builder /opt/venv /opt/venv

# Setup Fandol fonts
RUN mkdir -p /usr/local/share/fonts/fandol && \
    ln -s ${TL_ROOT}/texmf-dist/fonts/opentype/public/fandol/*.otf \
           /usr/local/share/fonts/fandol && \
    fc-cache -fv

# Create non-root user with home directory
RUN addgroup --system --gid 1000 appuser && \
    adduser --system --uid 1000 --gid 1000 --home /home/appuser --shell /bin/bash appuser

WORKDIR /app
COPY . /app

# Ensure ownership
RUN chown -R appuser:appuser /app

# Set HOME environment variable for TeX Live to find user directories
ENV HOME=/home/appuser

USER appuser
EXPOSE 8080

CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8080"]
