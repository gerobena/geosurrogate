"""Validation and exploitation figures (matplotlib, headless).

Wording note: K-S annotations use the rigorous formulation ("H0 not
rejected at significance level 0.05") — the test never demonstrates
distributional equality.
"""

from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

DPI = 150


def loocv_panel(actual: np.ndarray, pred: np.ndarray, sd: np.ndarray,
                metrics: dict, out: Path) -> None:
    # No figure-level title: the dashboard cards and the report sections
    # already label these figures and show the metrics.
    fig, axes = plt.subplots(1, 3, figsize=(16, 4.6))

    ax = axes[0]
    lims = [min(actual.min(), pred.min()), max(actual.max(), pred.max())]
    pad = 0.03 * (lims[1] - lims[0])
    lims = [lims[0] - pad, lims[1] + pad]
    ax.plot(lims, lims, "r--", lw=1.5, label="Ideal line (1:1)")
    ax.scatter(actual, pred, s=28, color="#1f3552", alpha=0.85, zorder=3)
    ax.set_xlim(lims), ax.set_ylim(lims)
    ax.set_xlabel("Actual SRF (FEM)"), ax.set_ylabel("Predicted SRF (surrogate)")
    ax.set_title("Predicted vs. Actual"), ax.legend(), ax.grid(alpha=0.3)

    ax = axes[1]
    resid = actual - pred
    ax.axhline(0, color="red", ls="--", lw=1.5)
    ax.scatter(actual, resid, s=28, color="#2980b9", alpha=0.85)
    ax.set_xlabel("Actual SRF (FEM)"), ax.set_ylabel("Error (actual - predicted)")
    ax.set_title("Residual plot"), ax.grid(alpha=0.3)

    ax = axes[2]
    order = np.argsort(actual)
    idx = np.arange(len(actual))
    ax.errorbar(idx, pred[order], yerr=2 * sd[order], fmt="o", ms=4,
                color="#8e44ad", ecolor="gray", elinewidth=1, capsize=2,
                label=r"Predicted mean $\pm 2\sigma$")
    ax.scatter(idx, actual[order], s=22, color="#c0392b", zorder=3,
               label="Actual value (FEM)")
    ax.set_xlabel("Case number (sorted by SRF)"), ax.set_ylabel("SRF")
    cov = metrics.get("coverage_2sd")
    ax.set_title(f"Probabilistic uncertainty coverage "
                 f"({100 * cov:.0f}% within $\\pm 2\\sigma$)")
    ax.legend(), ax.grid(alpha=0.3)

    fig.tight_layout()
    fig.savefig(out, dpi=DPI)
    plt.close(fig)


def massive_panel(actual: np.ndarray, pred: np.ndarray, metrics: dict,
                  out: Path) -> None:
    fig, axes = plt.subplots(1, 2, figsize=(12.5, 5))

    ax = axes[0]
    lims = [min(actual.min(), pred.min()), max(actual.max(), pred.max())]
    pad = 0.03 * (lims[1] - lims[0])
    lims = [lims[0] - pad, lims[1] + pad]
    ax.plot(lims, lims, "r--", lw=1.5, label="Ideal line (1:1)")
    ax.scatter(actual, pred, s=14, color="#1f3552", alpha=0.55)
    ax.set_xlim(lims), ax.set_ylim(lims)
    ax.set_xlabel("Actual SRF (FEM)"), ax.set_ylabel("Predicted SRF (surrogate)")
    ax.set_title(f"Predicted vs. actual ({metrics['n_test']} independent FEM results)")
    ax.legend(), ax.grid(alpha=0.3)

    ax = axes[1]
    bins = np.histogram_bin_edges(np.concatenate([actual, pred]), bins=30)
    ax.hist(actual, bins=bins, alpha=0.55, color="#c0392b", density=True,
            label="FEM (RS2)")
    ax.hist(pred, bins=bins, alpha=0.55, color="#2980b9", density=True,
            label="Surrogate")
    verdict = ("H0 rejected at alpha = 0.05"
               if metrics["ks_h0_rejected_at_005"]
               else "H0 not rejected at alpha = 0.05")
    ax.set_title(f"SRF distributions - two-sample K-S: {verdict}")
    ax.set_xlabel("SRF"), ax.set_ylabel("Density"), ax.legend(), ax.grid(alpha=0.3)

    fig.tight_layout()
    fig.savefig(out, dpi=DPI)
    plt.close(fig)


def ks_curve_panel(curve: pd.DataFrame, out: Path) -> None:
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(13, 5))

    ax1.plot(curve["n_train"], curve["ks_D"], "s-", color="#e67e22", lw=2, ms=6)
    ax1.axhline(0, color="green", ls="--", lw=1.5, label="Perfect agreement (D = 0)")
    ax1.fill_between(curve["n_train"], 0, curve["ks_D"], color="#e67e22", alpha=0.12)
    ax1.set_xlabel("Number of training simulations (FEM)")
    ax1.set_ylabel("K-S statistic D")
    ax1.set_title("Distributional discrepancy D vs. n")
    ax1.legend(), ax1.grid(alpha=0.3)

    ax2.plot(curve["n_train"], curve["ks_pvalue"], "o-", color="#2980b9", lw=2, ms=6)
    ax2.axhline(0.05, color="red", ls="--", lw=1.5,
                label="Significance level (alpha = 0.05)")
    top = max(1.0, curve["ks_pvalue"].max() + 0.05)
    ax2.fill_between(curve["n_train"], 0.05, top, color="#2ecc71", alpha=0.12,
                     label="H0 not rejected at alpha = 0.05")
    ax2.set_ylim(-0.03, top)
    ax2.set_xlabel("Number of training simulations (FEM)")
    ax2.set_ylabel("p-value")
    ax2.set_title("p-value vs. n (power-dependent; argue convergence with D)")
    ax2.legend(loc="lower right"), ax2.grid(alpha=0.3)

    fig.tight_layout()
    fig.savefig(out, dpi=DPI)
    plt.close(fig)


def mcs_histogram(srf: np.ndarray, threshold: float, metrics: dict, out: Path) -> None:
    fig, ax = plt.subplots(figsize=(9.5, 5.5))
    ax.hist(srf, bins=60, color="#2980b9", alpha=0.8, edgecolor="white")
    ax.axvline(threshold, color="red", ls="--", lw=2,
               label=f"Failure threshold (SRF = {threshold:g})")
    pof = metrics["pof"]
    ci = metrics["pof_ci95"]
    box = (f"n = {metrics['n_samples']:,}\n"
           f"mean = {metrics['srf_mean']:.3f}  std = {metrics['srf_std']:.3f}\n"
           f"P5 = {metrics['srf_p05']:.3f}  P95 = {metrics['srf_p95']:.3f}\n"
           f"PoF = P[SRF < {threshold:g}] = {pof:.4g}\n"
           f"95% CI [{ci[0]:.4g}, {ci[1]:.4g}]")
    ax.text(0.985, 0.97, box, transform=ax.transAxes, va="top", ha="right",
            fontsize=10, bbox=dict(boxstyle="round", fc="white", ec="gray", alpha=0.9))
    ax.set_xlabel("Predicted SRF (surrogate)"), ax.set_ylabel("Frequency")
    ax.set_title("Monte Carlo Simulation on the surrogate - SRF distribution",
                 fontweight="bold")
    ax.legend(loc="upper left"), ax.grid(alpha=0.3)
    fig.tight_layout()
    fig.savefig(out, dpi=DPI)
    plt.close(fig)
