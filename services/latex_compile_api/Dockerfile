FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

RUN set -eux; \
    apt-get update; \
    DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
      ca-certificates wget curl xz-utils perl make git ghostscript \
      fontconfig fonts-droid-fallback \
      fonts-noto-cjk; \
    rm -rf /var/lib/apt/lists/*

# Configure TeX Live environment variables
ENV TL_YEAR=2024
ENV TL_ROOT=/usr/local/texlive/${TL_YEAR}
ENV TL_BIN=${TL_ROOT}/bin/x86_64-linux
ENV PATH=${TL_BIN}:$PATH

ENV CTAN_MIRROR=https://ctan.math.utah.edu/ctan/tex-archive/

# Create TeX Live profile
RUN mkdir -p /tmp/tlinst && \
    echo 'selected_scheme scheme-full' > /tmp/texlive.profile && \
    echo 'TEXDIR /usr/local/texlive/2024' >> /tmp/texlive.profile && \
    echo 'TEXMFCONFIG ~/.texlive2024/texmf-config' >> /tmp/texlive.profile && \
    echo 'TEXMFHOME ~/.texlive2024/texmf' >> /tmp/texlive.profile && \
    echo 'TEXMFLOCAL /usr/local/texlive/texmf-local' >> /tmp/texlive.profile && \
    echo 'TEXMFSYSCONFIG /usr/local/texlive/2024/texmf-config' >> /tmp/texlive.profile && \
    echo 'TEXMFSYSVAR /usr/local/texlive/2024/texmf-var' >> /tmp/texlive.profile && \
    echo 'TEXMFVAR ~/.texlive2024/texmf-var' >> /tmp/texlive.profile && \
    echo 'binary_x86_64-linux 1' >> /tmp/texlive.profile && \
    echo 'collection-langchinese 1' >> /tmp/texlive.profile && \
    echo 'option_doc 0' >> /tmp/texlive.profile && \
    echo 'option_src 0' >> /tmp/texlive.profile && \
    echo 'option_autobackup 0' >> /tmp/texlive.profile && \
    echo 'option_desktop_integration 0' >> /tmp/texlive.profile && \
    echo 'option_file_assocs 0' >> /tmp/texlive.profile

# Install TeX Live 2024
RUN cd /tmp/tlinst && \
    echo "Downloading TeX Live installer..." && \
    wget --progress=dot:giga ${CTAN_MIRROR}/systems/texlive/tlnet/install-tl-unx.tar.gz && \
    tar -xzf install-tl-unx.tar.gz --strip-components=1 && \
    echo "Installing TeX Live (this will take 10-20 minutes)..." && \
    ./install-tl -profile /tmp/texlive.profile -repository ${CTAN_MIRROR}/systems/texlive/tlnet && \
    cd / && \
    rm -rf /tmp/tlinst /tmp/texlive.profile

# Install additional LaTeX packages
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
        trimspaces xstring unicode-math fontawesome6 roboto tikzfill  bookmark
 
RUN mkdir -p /usr/local/share/fonts/fandol && \
    ln -s /usr/local/texlive/2024/texmf-dist/fonts/opentype/public/fandol/*.otf \
           /usr/local/share/fonts/fandol && \
    fc-cache -fv

# Set environment variables
ENV MANPATH=/usr/local/texlive/2024/texmf-dist/doc/man:$MANPATH
ENV INFOPATH=/usr/local/texlive/2024/texmf-dist/doc/info:$INFOPATH

WORKDIR /app

COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

COPY . /app

EXPOSE 8080

CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8080"]
