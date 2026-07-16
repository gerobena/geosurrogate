# geosurrogate — demo dashboard image (Python + R + deepgp, NO RS2).
#
# The whole point of a container here is R: deepgp is compiled ONCE at image
# build time, so every runtime start is instant instead of fighting a cold-boot
# compile. This image runs the DEMO path only — the real RS2 workflow needs a
# licensed RS2 on a local Windows machine and cannot run in a container
# (see ARQUITECTURA.md). GEOSURROGATE_MODE=demo below makes the app hide the
# RS2 journey instead of offering a path that could only fail here.

FROM python:3.11-slim-bookworm

# --- System layer: R + the toolchain deepgp needs to compile its C++ once ------
#   r-base / r-base-dev      : the R runtime + headers to build R packages
#   build-essential, gfortran: C/C++/Fortran compilers used by Rcpp-based code
#   lib*-dev                 : system libs many CRAN packages link against
# Debian bookworm ships R 4.3.x; dev/CI use 4.5.3. deepgp behaves the same — the
# deepgp *package* version is what matters. Pin exact R via the CRAN apt repo if
# you ever need byte-for-byte parity.
RUN apt-get update && apt-get install -y --no-install-recommends \
        r-base \
        r-base-dev \
        build-essential \
        gfortran \
        libcurl4-openssl-dev \
        libssl-dev \
        libxml2-dev \
    && rm -rf /var/lib/apt/lists/*

# --- R layer: install deepgp (compiles here, then it is baked into the image) ---
# Isolated in its own layer so it is cached and never rebuilt unless this line
# changes — the slow step happens once.
RUN Rscript -e 'install.packages("deepgp", repos="https://cloud.r-project.org")' \
    && Rscript -e 'stopifnot(requireNamespace("deepgp", quietly=TRUE)); \
                   cat("deepgp", as.character(packageVersion("deepgp")), "\n")'

# --- Python layer: install the app and its UI extra ----------------------------
WORKDIR /app
# Copy only what the app needs at runtime. Explicit COPYs (plus .dockerignore)
# keep .venv/, runs/, .git/ and any .fez out of the image.
COPY pyproject.toml README.md ./
COPY src/ ./src/
COPY app/ ./app/
COPY demo_cases/ ./demo_cases/
RUN python -m pip install --upgrade pip \
    && pip install -e ".[ui]"

# --- Runtime configuration -----------------------------------------------------
# GEOSURROGATE_RSCRIPT points the config's R bridge at the container's Rscript
# (the same override CI uses, instead of the author's Windows path).
# The STREAMLIT_* vars make the server reachable from outside the container and
# stop it trying to open a browser or phone home.
ENV GEOSURROGATE_RSCRIPT=Rscript \
    GEOSURROGATE_MODE=demo \
    STREAMLIT_SERVER_ADDRESS=0.0.0.0 \
    STREAMLIT_SERVER_HEADLESS=true \
    STREAMLIT_BROWSER_GATHER_USAGE_STATS=false

# Per-run working folders (state.json, events.jsonl, dataset.csv, figures) land
# here. Ephemeral by design — a restart wipes demo runs, which is fine.
RUN mkdir -p runs

EXPOSE 8501

# Liveness probe against Streamlit's built-in health endpoint.
HEALTHCHECK --interval=30s --timeout=5s --start-period=45s --retries=3 \
    CMD python -c "import urllib.request,sys; \
        sys.exit(0 if urllib.request.urlopen('http://localhost:8501/_stcore/health').read()==b'ok' else 1)"

CMD ["streamlit", "run", "app/Home.py", "--server.port=8501"]
