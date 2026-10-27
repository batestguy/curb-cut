# Survey-weighted proportions for Curb Cut, with Korn-Graubard intervals.
#
# Usage: Rscript packages/ingest/R/estimate.R <spec.json>
# Run by curbcut_ingest.aggregate, which writes the spec and an analysis-ready Parquet
# (design columns plus 0/1 indicator columns) under data/restricted/derived/. The output
# CSV also stays in data/restricted/derived/: it holds every cell, including those under
# the disclosure threshold, so it goes through curbcut_ingest.disclosure before anything
# is published.
#
# Data-handling rule: this script prints only counts of rows and cells, never a value.
#
# Design: svydesign(ids = ~psu, strata = ~stratum, weights = ~weight, nest = TRUE).
# Lonely PSUs: options(survey.lonely.psu = "adjust") (a stratum with one PSU contributes
# its deviation from the grand mean), and survey.adjust.domain.lonely = TRUE applies the
# same adjustment when a domain has one PSU in a stratum.
#
# Each spec group crosses one or more `by` columns (e.g. state x sex, zone x sector); the
# output columns geography, sex and breakdown_level take their levels, and breakdown names
# the extra dimension ("all" when there is none).
#
# Per cell (NCHS Data Presentation Standards for Proportions, docs/verification.md D42):
#   estimate, se       svymean of the 0/1 indicator over the domain (Taylor linearisation)
#   n_unweighted       respondents in the domain with the indicator answered
#   n_events           unweighted respondents with the indicator = 1 (not published)
#   df                 PSUs with at least one respondent in the domain, minus the strata
#                      holding them (NCHS rule of thumb for subgroups)
#   n_effective        p(1 - p) / se^2, capped at n; n when p is 0 or 1
#   ci_low, ci_high    Korn-Graubard 95%: Clopper-Pearson with the effective n scaled by
#                      (t_{n-1} / t_df)^2 (Korn and Graubard 1998)

suppressWarnings(suppressPackageStartupMessages({
  library(survey)
}))

options(survey.lonely.psu = "adjust", survey.adjust.domain.lonely = TRUE)

korn_graubard <- function(p, n_eff, n, df, level = 0.95) {
  alpha <- 1 - level
  if (is.na(df) || df < 1 || is.na(p)) return(c(NA_real_, NA_real_))
  scale <- if (n > 1) (qt(1 - alpha / 2, n - 1) / qt(1 - alpha / 2, df))^2 else 1
  m <- n_eff * min(scale, 1)
  x <- p * m
  lo <- if (x <= 0) 0 else qbeta(alpha / 2, x, m - x + 1)
  hi <- if (x >= m) 1 else qbeta(1 - alpha / 2, x + 1, m - x)
  c(lo, hi)
}

estimate_group <- function(design, data, group) {
  # group$by: one or more columns to cross; group$targets: the output column that takes
  # each one's levels (geography, sex or breakdown_level), in the same order.
  by <- unlist(group$by)
  targets <- unlist(group$targets)
  keep <- rep(TRUE, nrow(data))
  for (column in by) keep <- keep & !is.na(data[[column]])
  for (column in names(group$filter)) {
    keep <- keep & !is.na(data[[column]]) & data[[column]] == group$filter[[column]]
  }
  rows <- list()
  for (y in unlist(group$outcomes)) {
    ok <- keep & !is.na(data[[y]])
    if (!any(ok)) next
    sub <- subset(design, ok)
    fit <- svyby(as.formula(paste0("~", y)), as.formula(paste0("~", paste(by, collapse = "+"))),
                 sub, svymean, keep.var = TRUE)
    p <- unname(coef(fit))
    se <- unname(SE(fit))
    for (i in seq_len(nrow(fit))) {
      cell <- ok
      labels <- group$labels
      for (j in seq_along(by)) {
        level <- as.character(fit[[by[j]]][i])
        cell <- cell & data[[by[j]]] == level
        labels[[targets[j]]] <- level
      }
      n <- sum(cell)
      events <- sum(data[[y]][cell] == 1)
      psus <- unique(data[cell, c("stratum", "psu")])
      df <- nrow(psus) - length(unique(psus$stratum))
      n_eff <- if (p[i] <= 0 || p[i] >= 1 || se[i] <= 0) n else min(n, p[i] * (1 - p[i]) / se[i]^2)
      ci <- korn_graubard(p[i], n_eff, n, df)
      rows[[length(rows) + 1]] <- data.frame(
        measure = y,
        geography_level = labels$geography_level,
        geography = labels$geography,
        age_group = labels$age_group,
        sex = labels$sex,
        breakdown = labels$breakdown,
        breakdown_level = labels$breakdown_level,
        estimate = p[i],
        se = se[i],
        ci_low = ci[1],
        ci_high = ci[2],
        n_unweighted = n,
        n_events = events,
        n_effective = n_eff,
        df = df,
        stringsAsFactors = FALSE
      )
    }
  }
  do.call(rbind, rows)
}

main <- function(spec_path) {
  spec <- jsonlite::read_json(spec_path)
  data <- as.data.frame(nanoparquet::read_parquet(spec$input))
  complete <- !is.na(data$weight) & data$weight > 0 & !is.na(data$psu) & !is.na(data$stratum)
  cat(sprintf("estimate.R: %d rows, %d dropped for missing design variables\n",
              nrow(data), sum(!complete)))
  data <- data[complete, ]
  design <- svydesign(ids = ~psu, strata = ~stratum, weights = ~weight, data = data,
                      nest = TRUE)
  out <- do.call(rbind, lapply(spec$groups, function(g) estimate_group(design, data, g)))
  dir.create(dirname(spec$output), showWarnings = FALSE, recursive = TRUE)
  write.csv(out, spec$output, row.names = FALSE, na = "")
  cat(sprintf("estimate.R: wrote %d cells\n", nrow(out)))
}

args <- commandArgs(trailingOnly = TRUE)
if (length(args) != 1) stop("usage: Rscript estimate.R <spec.json>")
main(args[1])
