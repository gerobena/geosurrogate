---
title: geosurrogate demo
emoji: ⛰️
colorFrom: blue
colorTo: gray
sdk: docker
app_port: 8501
pinned: false
license: mit
short_description: Active-learning GP surrogates for slope-stability reliability
---

# geosurrogate — public demo

Interactive demo of **geosurrogate**: active-learning Gaussian-Process surrogates
for probabilistic slope-stability analysis. It builds a validated surrogate of a
geotechnical FEM model and exploits it for massive Monte Carlo reliability
analysis (probability of failure) at a fraction of the FEM cost.

This Space runs the **demo cases only** — every value served comes from real,
precomputed RS2 finite-element results. The from-zero workflow on your own model
needs a licensed RS2 on a local Windows machine and is not available here.

Source code, architecture and full documentation:
**https://github.com/gerobena/geosurrogate**
