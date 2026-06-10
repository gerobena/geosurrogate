# geosurrogate R worker — fit GP (deepgp), predict, score ALC.
# Contract (see ARQUITECTURA.md §6.2): inputs/outputs are CSV files inside a
# work directory; all scaling happens on the Python side, so this script is
# agnostic to dimensionality and variable names.
#
# Usage: Rscript fit_predict_alc.R <workdir> <nmcmc> <burn> <thin> <seed> <kernel> <sep01> <alc01>
# Reads : workdir/train.csv    columns x*, y          (X in [0,1]^D, y standardized)
#         workdir/predict.csv  columns x*, set        (set in {cand, valid})
# Writes: workdir/predictions.csv  columns mean, s2   (one row per predict.csv row)
#         workdir/alc.csv          column  alc        (one row per 'cand' row)
#         workdir/diagnostics.json timings and sizes

args <- commandArgs(trailingOnly = TRUE)
if (length(args) < 8) stop("expected: workdir nmcmc burn thin seed kernel sep01 alc01")
workdir <- args[1]
nmcmc   <- as.integer(args[2])
burn    <- as.integer(args[3])
thin    <- as.integer(args[4])
seed    <- as.integer(args[5])
kernel  <- args[6]
sep     <- as.integer(args[7]) == 1L
do_alc  <- as.integer(args[8]) == 1L

suppressPackageStartupMessages({
  library(deepgp)
  library(parallel)
})

train <- read.csv(file.path(workdir, "train.csv"))
pred  <- read.csv(file.path(workdir, "predict.csv"))

xcols <- setdiff(names(train), "y")
X  <- as.matrix(train[, xcols, drop = FALSE])
y  <- as.numeric(train$y)
Xp <- as.matrix(pred[, xcols, drop = FALSE])

set.seed(seed)
t0 <- Sys.time()
fit <- fit_one_layer(x = X, y = y, nmcmc = nmcmc, sep = sep, cov = kernel,
                     vecchia = FALSE, g = 1e-3, verb = FALSE)
fit <- trim(fit, burn = burn, thin = thin)
t1 <- Sys.time()

n_cores <- max(1L, parallel::detectCores() - 1L)
p <- predict(fit, Xp, cores = n_cores, lite = TRUE)
write.csv(data.frame(mean = p$mean, s2 = p$s2),
          file.path(workdir, "predictions.csv"), row.names = FALSE)
t2 <- Sys.time()

alc_s <- "null"
if (do_alc) {
  cand_idx <- which(pred$set == "cand")
  a <- ALC(fit, x_new = Xp[cand_idx, , drop = FALSE])
  write.csv(data.frame(alc = a$value), file.path(workdir, "alc.csv"), row.names = FALSE)
  alc_s <- sprintf("%.2f", as.numeric(difftime(Sys.time(), t2, units = "secs")))
}

diag <- sprintf('{"n_train": %d, "n_predict": %d, "fit_s": %.2f, "predict_s": %.2f, "alc_s": %s}',
                nrow(X), nrow(Xp),
                as.numeric(difftime(t1, t0, units = "secs")),
                as.numeric(difftime(t2, t1, units = "secs")), alc_s)
writeLines(diag, file.path(workdir, "diagnostics.json"))
