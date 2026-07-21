# Third-party notices

geosurrogate itself is released under the MIT License (see `LICENSE`). The
distributed builds additionally **redistribute third-party software**, each under
its own licence. This file records what ships and the obligations that come with
it.

> Not legal advice. If you distribute the native installer commercially, have a
> professional confirm this is complete for your situation.

## What ships in each build

| Build | Bundles |
|---|---|
| Source install (`pip install`) | nothing third-party is redistributed — pip fetches dependencies directly |
| Docker demo image (`ghcr.io/gerobena/geosurrogate`) | Debian base, R, deepgp and CRAN dependencies, Python packages |
| Native Windows installer | R + CRAN packages (`R/`), CPython + Python packages (`python/`) |

RS2 (Rocscience) is **never** bundled or redistributed. It is the user's own
licensed software; geosurrogate only connects to an installation already present
on the machine.

## R and CRAN packages

The bundled R runtime is redistributed under the **GNU General Public License,
version 2**. The complete licence text ships with the bundle as `R/COPYING`, and
a generated per-package inventory (name, version, licence) as
`R/THIRD-PARTY-R.md` — produced by `tools/build_r_bundle.py` from the bundle
itself, so it always matches what is actually distributed.

Bundled packages carry a mix of GPL-2, GPL-3, GPL (>= 2), LGPL, MIT, Apache-2.0,
BSD-3-Clause and BSL-1.0 terms; the inventory lists the exact licence for each.

**Source code offer.** Complete corresponding source for R is published by the R
Foundation at <https://cran.r-project.org/src/base/>, and for every bundled
package at `https://cran.r-project.org/package=<name>`. The publisher of this
bundle will additionally provide the corresponding source on request, for as long
as the build is distributed — open an issue at
<https://github.com/gerobena/geosurrogate/issues>.

## Python and Python packages

The native installer bundles CPython (Python Software Foundation License) and the
runtime dependencies declared in `pyproject.toml` (`pydantic`, `PyYAML`, `typer`,
`numpy`, `pandas`, `scipy`, `scikit-learn`, `openpyxl`, `matplotlib`, `streamlit`,
`plotly` and their transitive dependencies), each under its own licence —
predominantly MIT, BSD and Apache-2.0. Run
`python\python.exe -m pip list` inside the bundle for the exact set and versions
that shipped with your copy.

## RS2Scripting

`RS2Scripting` is published by Rocscience on PyPI and is **not** bundled. The
launcher installs the version matching the user's own RS2 installation on first
run, directly from PyPI, subject to Rocscience's terms.
