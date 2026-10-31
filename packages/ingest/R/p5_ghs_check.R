# P5 E1 cross-check (pre-registration section 8): the change-score regression in R.
#
# Usage: Rscript packages/ingest/R/p5_ghs_check.R <spec.json>
# Run by curbcut_ingest.restricted.p5_ghs.r_change_model, which writes the spec and a
# Parquet with y (the change), onset, the W4 covariates, weight (longitudinal) and cluster
# (EA). The output JSON stays next to it, in the restricted zone (or a test folder).
#
# Model: fixest::feols(y ~ onset + covariates as factors, weights = longitudinal weight,
# cluster = EA), the same as pyfixest feols with CRV1 errors in p5_ghs.change_model.
#
# Data-handling rule: this script prints only counts (lines start with "p5_ghs_check.R: ").

suppressWarnings(suppressPackageStartupMessages({
  library(fixest)
}))

main <- function(spec_path) {
  spec <- jsonlite::read_json(spec_path)
  data <- as.data.frame(nanoparquet::read_parquet(spec$input))
  covariates <- unlist(spec$covariates)
  for (column in c(covariates, "cluster")) data[[column]] <- factor(data[[column]])
  cat(sprintf("p5_ghs_check.R: %d rows, %d clusters\n", nrow(data),
              length(unique(data$cluster))))
  formula <- as.formula(paste("y ~ onset +", paste(covariates, collapse = " + ")))
  fit <- feols(formula, data = data, weights = ~weight, cluster = ~cluster, notes = FALSE)
  ci <- confint(fit, parm = "onset", level = 0.95)
  out <- list(
    estimate = unname(coef(fit)["onset"]),
    se = unname(se(fit)["onset"]),
    ci_low = unname(ci[1, 1]),
    ci_high = unname(ci[1, 2]),
    n = nobs(fit),
    fixest = as.character(packageVersion("fixest"))
  )
  dir.create(dirname(spec$output), showWarnings = FALSE, recursive = TRUE)
  jsonlite::write_json(out, spec$output, auto_unbox = TRUE, digits = NA, pretty = TRUE)
  cat("p5_ghs_check.R: wrote 1 estimate\n")
}

args <- commandArgs(trailingOnly = TRUE)
if (length(args) != 1) stop("usage: Rscript p5_ghs_check.R <spec.json>")
main(args[1])
