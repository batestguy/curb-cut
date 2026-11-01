# P5 benchmark and sensemakr (pre-registration sections 5.2 and 5.3).
#
# Usage: Rscript packages/ingest/R/p5_benchmark.R <spec.json>
# Run by curbcut_ingest.restricted.p5_mpi.r_benchmark, which writes the spec and an
# analysis-ready Parquet (outcome y, exposure d, covariates, cluster, state, pop_wgt) under
# data/restricted/derived/p5/ (or a test's temporary folder). The output JSON stays there.
#
# Data-handling rule: this script prints only counts, never a value (lines start with
# "p5_benchmark.R: "; everything else R prints is withheld by the Python caller).
#
# 5.2 Benchmark: survey-weighted linear probability model, svyglm(y ~ d + covariates),
#     design: ids = EA (cluster), strata = state, weights = population weight. Every EA
#     is nested in one state (pre-registration 3.1). Lonely PSUs: "adjust", as estimate.R.
# 5.3 sensemakr (Cinelli and Hazlett 2020) on lm() with the same covariates, weighted by
#     the population weight normalised to mean 1 (sensemakr does not take svyglm; this
#     model ignores the design), benchmarked on the head's education (all its dummies as
#     one group), kd = 1, 2, 3.

suppressWarnings(suppressPackageStartupMessages({
  library(survey)
  library(sensemakr)
}))

options(survey.lonely.psu = "adjust")

main <- function(spec_path) {
  spec <- jsonlite::read_json(spec_path)
  data <- as.data.frame(nanoparquet::read_parquet(spec$input))
  covariates <- unlist(spec$covariates)
  categorical <- unlist(spec$categorical)
  for (column in categorical) data[[column]] <- factor(data[[column]])
  data$w_norm <- data$pop_wgt / mean(data$pop_wgt)
  cat(sprintf("p5_benchmark.R: %d rows, %d clusters, %d strata\n",
              nrow(data), length(unique(data$cluster)), length(unique(data$state))))

  formula <- as.formula(paste("y ~ d +", paste(covariates, collapse = " + ")))

  design <- svydesign(ids = ~cluster, strata = ~state, weights = ~pop_wgt, data = data,
                      nest = TRUE)
  fit <- svyglm(formula, design = design)
  ci <- confint(fit, parm = "d", df = degf(design))
  lpm <- list(
    estimate = unname(coef(fit)["d"]),
    se = unname(SE(fit)["d"]),
    ci_low = unname(ci[1, 1]),
    ci_high = unname(ci[1, 2]),
    df = degf(design)
  )

  model <- lm(formula, data = data, weights = w_norm)
  bench <- grep(paste0("^", spec$benchmark), names(coef(model)), value = TRUE)
  bench <- bench[!is.na(coef(model)[bench])]
  groups <- list()
  groups[[spec$benchmark]] <- bench
  sens <- sensemakr(model = model, treatment = "d", benchmark_covariates = groups,
                    kd = 1:3)
  stats <- sens$sensitivity_stats
  bounds <- sens$bounds
  out <- list(
    survey_lpm = lpm,
    sensemakr = list(
      estimate = unname(stats$estimate),
      se = unname(stats$se),
      partial_r2_yd_x = unname(stats$r2yd.x),
      rv_q = unname(stats$rv_q),
      rv_qa = unname(stats$rv_qa),
      benchmark = spec$benchmark,
      benchmark_terms = length(bench),
      bounds = lapply(seq_len(nrow(bounds)), function(i) list(
        label = as.character(bounds$bound_label[i]),
        r2dz_x = bounds$r2dz.x[i],
        r2yz_dx = bounds$r2yz.dx[i],
        adjusted_estimate = bounds$adjusted_estimate[i],
        adjusted_lower_ci = bounds$adjusted_lower_CI[i],
        adjusted_upper_ci = bounds$adjusted_upper_CI[i]
      ))
    ),
    versions = list(
      survey = as.character(packageVersion("survey")),
      sensemakr = as.character(packageVersion("sensemakr")),
      r = paste(R.version$major, R.version$minor, sep = ".")
    )
  )
  dir.create(dirname(spec$output), showWarnings = FALSE, recursive = TRUE)
  jsonlite::write_json(out, spec$output, auto_unbox = TRUE, digits = NA, pretty = TRUE)
  cat(sprintf("p5_benchmark.R: wrote %d sensemakr bounds\n", nrow(bounds)))
}

args <- commandArgs(trailingOnly = TRUE)
if (length(args) != 1) stop("usage: Rscript p5_benchmark.R <spec.json>")
main(args[1])
