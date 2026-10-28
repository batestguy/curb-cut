# Arcsine Fay-Herriot small-area estimates of adult disability prevalence by state.
#
# Usage: Rscript packages/ingest/R/fay_herriot.R <spec.json>
# Run by curbcut_ingest.sae, which writes the spec. Inputs are public files only: the
# disclosure-gated DHS 2024 state aggregates, the state covariates and the geoBoundaries
# polygons. The rules (covariates, selection, failure tests) were fixed before any fit,
# in docs/fay-herriot-covariates.md; this script implements them and nothing else.
#
# Steps:
#   1. y = asin(sqrt(p)); its direct variance is 1 / (4 n_eff) (delta method).
#   2. GVF: log(var_y) ~ log(n_unweighted); smoothed psi = exp(fit) * exp(s^2 / 2).
#   3. Every subset of the standardised covariates with at most `max_covariates` terms,
#      fitted by ML (sae::eblupFH); lowest BIC wins, ties within `bic_tie` go to fewer terms.
#   4. Diagnostics on the chosen model; on failure, the next model by BIC.
#   5. Final REML fit; bias-corrected back-transform E[sin^2(theta)], theta ~ N(eblup, g*psi):
#      (1 - exp(-2 v) cos(2 eblup)) / 2 with v = g * psi, g = s2u / (s2u + psi).
#   6. Ratio benchmark to the national direct estimate with adult-population weights.
#   7. Parametric bootstrap MSE of the back-transformed estimator (B draws, fixed seed).
#   8. Spatial FH (sae::eblupSFH, row-standardised queen contiguity) against plain FH on
#      analytic MSE on the arcsine scale.

suppressWarnings(suppressPackageStartupMessages({
  library(sae)
  library(spdep)
  library(sf)
  library(jsonlite)
}))

# Outputs are committed, so write LF line endings on every platform.
write_json_lf <- function(x, path) {
  con <- file(path, "wb")
  on.exit(close(con))
  writeLines(toJSON(x, auto_unbox = TRUE, pretty = TRUE, digits = 8), con, sep = "
")
}

write_csv_lf <- function(x, path) {
  con <- file(path, "wb")
  on.exit(close(con))
  write.csv(x, con, row.names = FALSE)
}

back_transform <- function(theta, v) (1 - exp(-2 * v) * cos(2 * theta)) / 2

fit_fh <- function(formula, data, method) {
  fit <- eblupFH(formula, vardir = psi, method = method, data = data)
  if (!isTRUE(fit$fit$convergence)) stop("FH fit did not converge: ", deparse(formula))
  fit
}

model_formula <- function(terms) {
  rhs <- if (length(terms) == 0) "1" else paste(terms, collapse = " + ")
  as.formula(paste("y ~", rhs))
}

diagnose <- function(fit, data, terms, large) {
  X <- model.matrix(model_formula(terms), data)
  beta <- fit$fit$estcoef$beta
  s2u <- fit$fit$refvar
  resid <- (data$y - drop(X %*% beta)) / sqrt(s2u + data$psi)
  shapiro <- shapiro.test(resid)$p.value
  g <- s2u / (s2u + data$psi)
  p_model <- back_transform(drop(fit$eblup), g * data$psi)
  outside <- p_model < data$ci_low | p_model > data$ci_high
  list(
    shapiro_p = shapiro,
    outside_large = sum(outside[large]),
    outside_states = data$geography[outside],
    pass = shapiro >= 0.05 && sum(outside[large]) <= 2
  )
}

bootstrap_mse <- function(terms, data, beta, s2u, B, seed) {
  set.seed(seed)
  X <- model.matrix(model_formula(terms), data)
  mu <- drop(X %*% beta)
  m <- nrow(data)
  err <- matrix(NA_real_, B, m)
  failed <- 0L
  for (b in seq_len(B)) {
    theta <- mu + rnorm(m, 0, sqrt(s2u))
    star <- data
    star$y <- theta + rnorm(m, 0, sqrt(data$psi))
    fit <- tryCatch(fit_fh(model_formula(terms), star, "REML"), error = function(e) NULL)
    if (is.null(fit)) {
      failed <- failed + 1L
      next
    }
    g <- fit$fit$refvar / (fit$fit$refvar + data$psi)
    err[b, ] <- back_transform(drop(fit$eblup), g * data$psi) - sin(theta)^2
  }
  list(mse = colMeans(err^2, na.rm = TRUE), failed = failed)
}

main <- function(spec_path) {
  spec <- fromJSON(spec_path)
  direct <- read.csv(spec$outcome_csv, stringsAsFactors = FALSE)
  direct <- direct[
    direct$measure == spec$measure & direct$age_group == spec$age_group &
      direct$sex == "all" & direct$breakdown == "all",
  ]
  national <- read.csv(spec$national_csv, stringsAsFactors = FALSE)
  national <- national[
    national$measure == spec$measure & national$age_group == spec$age_group &
      national$sex == "all" & national$breakdown == "all",
  ]
  stopifnot(nrow(national) == 1)
  covariates <- read.csv(spec$covariates_csv, stringsAsFactors = FALSE)
  data <- merge(direct, covariates, by.x = "geography", by.y = spec$covariate_key)
  stopifnot(nrow(data) == 37, all(!is.na(data$estimate)), all(data$estimate > 0))
  data <- data[order(data$geography), ]

  # 1-2. Arcsine scale and GVF.
  data$y <- asin(sqrt(data$estimate))
  data$var_direct <- 1 / (4 * data$n_effective)
  gvf <- lm(log(var_direct) ~ log(n_unweighted), data = data)
  data$psi <- exp(fitted(gvf)) * exp(summary(gvf)$sigma^2 / 2)

  covs <- spec$covariates
  for (column in covs) data[[paste0("z_", column)]] <- as.numeric(scale(data[[column]]))
  candidates <- paste0("z_", covs)

  # 3. All subsets up to max_covariates, ML, BIC.
  subsets <- list(character(0))
  for (k in seq_len(spec$max_covariates)) {
    subsets <- c(subsets, combn(candidates, k, simplify = FALSE))
  }
  table <- do.call(rbind, lapply(subsets, function(terms) {
    fit <- fit_fh(model_formula(terms), data, "ML")
    beta <- fit$fit$estcoef
    data.frame(
      terms = if (length(terms) == 0) "(intercept only)" else paste(sub("^z_", "", terms), collapse = " + "),
      n_terms = length(terms),
      loglike = fit$fit$goodness[["loglike"]],
      bic = fit$fit$goodness[["BIC"]],
      sigma2_u = fit$fit$refvar,
      coefficients = paste(sprintf("%s=%.4f (p=%.3f)", sub("^z_", "", rownames(beta)), beta$beta, beta$pvalue), collapse = "; "),
      stringsAsFactors = FALSE
    )
  }))
  # Ranking: BIC, with a model within bic_tie of a better one losing to it only if larger.
  table <- table[order(table$bic, table$n_terms), ]
  best <- table$bic[1]
  near <- table$bic - best <= spec$bic_tie
  fewest <- min(table$n_terms[near])
  table$rank <- NA_integer_
  first <- which(near & table$n_terms == fewest)[1]
  order_idx <- c(first, setdiff(seq_len(nrow(table)), first))
  table <- table[order_idx, ]
  table$rank <- seq_len(nrow(table))

  # 4. Diagnostics, in rank order, until one passes.
  large <- rank(-data$n_unweighted, ties.method = "first") <= 12
  chosen <- NULL
  tried <- list()
  for (i in seq_len(nrow(table))) {
    terms <- if (table$n_terms[i] == 0) character(0) else paste0("z_", strsplit(table$terms[i], " \\+ ")[[1]])
    fit <- fit_fh(model_formula(terms), data, "REML")
    d <- diagnose(fit, data, terms, large)
    tried[[length(tried) + 1]] <- list(
      terms = table$terms[i], bic = table$bic[i], shapiro_p = d$shapiro_p,
      outside_large = d$outside_large, outside_states = d$outside_states, pass = d$pass
    )
    if (d$pass) {
      chosen <- list(terms = terms, fit = fit, diag = d, label = table$terms[i])
      break
    }
  }
  if (is.null(chosen)) {
    dir.create(spec$out_dir, showWarnings = FALSE, recursive = TRUE)
    write_csv_lf(table, file.path(spec$out_dir, "fh_model_selection.csv"))
    write_json_lf(tried, file.path(spec$out_dir, "fh_diagnostics_failed.json"))
    stop("no model passed the diagnostics")
  }

  # 5. Final estimates.
  fit <- chosen$fit
  s2u <- fit$fit$refvar
  beta <- fit$fit$estcoef$beta
  g <- s2u / (s2u + data$psi)
  data$theta_fh <- drop(fit$eblup)
  data$fh <- back_transform(data$theta_fh, g * data$psi)
  data$gamma <- g

  # 6. Benchmark.
  w <- data[[spec$weight_column]] / sum(data[[spec$weight_column]])
  ratio <- national$estimate / sum(w * data$fh)
  data$fh_benchmarked <- data$fh * ratio

  # 7. Bootstrap MSE.
  boot <- bootstrap_mse(chosen$terms, data, beta, s2u, spec$bootstrap_b, spec$seed)
  data$fh_mse <- boot$mse
  data$fh_cv <- sqrt(boot$mse) / data$fh
  data$direct_cv <- data$se / data$estimate
  data$use_direct <- data$fh < data$ci_low | data$fh > data$ci_high

  # 8. Spatial FH.
  shapes <- st_read(spec$boundaries, quiet = TRUE)
  shapes$geography <- shapes[[spec$boundary_key]]
  stopifnot(!any(is.na(shapes$geography)))
  shapes <- shapes[match(data$geography, shapes$geography), ]
  nb <- poly2nb(shapes, queen = TRUE)
  W <- nb2mat(nb, style = "W", zero.policy = TRUE)
  formula <- model_formula(chosen$terms)
  sfh <- eblupSFH(formula, vardir = psi, proxmat = W, method = "REML", data = data)
  mse_fh <- mseFH(formula, vardir = psi, method = "REML", data = data)$mse
  mse_sfh <- mseSFH(formula, vardir = psi, proxmat = W, method = "REML", data = data)$mse
  data$theta_sfh <- drop(sfh$eblup)
  data$mse_theta_fh <- mse_fh
  data$mse_theta_sfh <- mse_sfh

  out <- data.frame(
    geography = data$geography,
    direct = data$estimate, direct_se = data$se, direct_cv = data$direct_cv,
    direct_ci_low = data$ci_low, direct_ci_high = data$ci_high,
    n_unweighted = data$n_unweighted, psi_smoothed = data$psi, gamma = data$gamma,
    fh = data$fh, fh_benchmarked = data$fh_benchmarked,
    fh_rmse = sqrt(data$fh_mse), fh_cv = data$fh_cv,
    use_direct = data$use_direct,
    mse_theta_fh = data$mse_theta_fh, mse_theta_sfh = data$mse_theta_sfh,
    sfh = back_transform(data$theta_sfh, data$gamma * data$psi)
  )
  dir.create(spec$out_dir, showWarnings = FALSE, recursive = TRUE)
  write_csv_lf(out, file.path(spec$out_dir, "fh_state.csv"))
  write_csv_lf(table, file.path(spec$out_dir, "fh_model_selection.csv"))
  summary <- list(
    measure = spec$measure, age_group = spec$age_group,
    gvf = list(intercept = unname(coef(gvf)[1]), slope = unname(coef(gvf)[2]), sigma = summary(gvf)$sigma, r2 = summary(gvf)$r.squared),
    chosen = chosen$label, diagnostics_tried = tried,
    sigma2_u = s2u, coefficients = fit$fit$estcoef,
    shapiro_p = chosen$diag$shapiro_p, outside_large = chosen$diag$outside_large,
    states_using_direct = data$geography[data$use_direct],
    benchmark = list(national_direct = national$estimate, ratio = ratio, weight_column = spec$weight_column),
    bootstrap = list(B = spec$bootstrap_b, seed = spec$seed, failed = boot$failed),
    median_cv = list(direct = median(data$direct_cv), fh = median(data$fh_cv)),
    spatial = list(
      rho = sfh$fit$spatialcorr,
      neighbours_min = min(card(nb)),
      median_mse_theta = list(fh = median(mse_fh), sfh = median(mse_sfh)),
      states_sfh_better = sum(mse_sfh < mse_fh)
    )
  )
  write_json_lf(summary, file.path(spec$out_dir, "fh_summary.json"))
  cat("fay_herriot: wrote", nrow(out), "states;", nrow(table), "models compared\n")
}

args <- commandArgs(trailingOnly = TRUE)
if (length(args) != 1) stop("usage: Rscript fay_herriot.R <spec.json>")
main(args[[1]])
