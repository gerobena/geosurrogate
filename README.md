# geosurrogate

Active-learning Gaussian Process surrogates for probabilistic slope stability analysis. Builds a validated surrogate of a geotechnical FEM model (RS2 first; PLAXIS/FLAC planned) and exploits it for massive Monte Carlo reliability analyses at a fraction of the FEM cost.

> **Status: private prototype (F1).** Architecture and roadmap in [ARQUITECTURA.md](ARQUITECTURA.md).

## Quickstart (demo mode — no RS2 license required)

```
python -m venv .venv
.venv\Scripts\activate
pip install -e .[dev]
geosurrogate demo list
geosurrogate demo run slope_2d --fast
```

The live demo retrains the GP with R/deepgp at each iteration; it requires a local R installation (tested with R 4.5.3 + deepgp 1.2.1):

```r
install.packages("deepgp")
```

Every SRF value served in demo mode is a real RS2 finite-element result from a precomputed pool — no interpolated ground truth.

## Layout

- `src/geosurrogate/` — core package (UI-agnostic)
- `app/` — Streamlit dashboard (F2)
- `demo_cases/` — packaged demo datasets (derived data only; no `.fez` files)
- `tools/` — one-off maintenance scripts (demo case packaging)
- `tests/` — unit tests + end-to-end demo test
