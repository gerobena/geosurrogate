# HuggingFace Space image for the geosurrogate PUBLIC DEMO.
#
# It reuses the exact image built and tested in CI (ghcr.io/gerobena/
# geosurrogate) instead of recompiling deepgp here, and only adapts it to the
# Space runtime: HuggingFace runs containers as user id 1000 and needs a
# writable HOME for Streamlit's config/cache and the per-run working folders.
#
# Prerequisite: the GHCR package must be PUBLIC so HuggingFace's builder can
# pull it anonymously (GitHub -> your packages -> geosurrogate -> Package
# settings -> Change visibility -> Public). See DEPLOY.md.
FROM ghcr.io/gerobena/geosurrogate:latest

ENV HOME=/app
RUN chown -R 1000:1000 /app
USER 1000

# GEOSURROGATE_MODE=demo and the Streamlit CMD (serving on 8501) are already set
# in the base image, so the RS2 journey stays hidden and the dashboard is served
# on the port declared as app_port in this Space's README.
