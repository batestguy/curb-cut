# Spatial analysis of the DHS 2024 direct state estimates (P4a step 3).
#
# Usage: Rscript packages/ingest/R/spatial.R <spec.json>
# Run by curbcut_ingest.spatial, which writes the spec. Inputs are public files only: the
# disclosure-gated DHS 2024 state aggregates, the geoBoundaries polygons and the GRID3 facility
# counts per state (curbcut_ingest.grid3). Fay-Herriot failed its diagnostics (D56), so every
# method here runs on the direct survey estimates. Never on JONAPWD (D17).
#
# Steps:
#   1. Queen contiguity (spdep::poly2nb) from the simplified polygons; checks: every state has
#      a neighbour, the list is symmetric, known pairs are adjacent. Row-standardised weights.
#   2. Global Moran's I (spdep::moran.mc, one-sided "greater", nsim permutations, fixed seed)
#      for each measure in the spec; Benjamini-Hochberg across them.
#   3. LISA (spdep::localmoran_perm, two-sided, conditional permutations, same seed) on one
#      measure; Benjamini-Hochberg across the states; quadrant classes. Exploratory.
#   4. Ward.D2 clustering of the standardised domain profiles; k by mean silhouette. Descriptive.
#   5. Spearman correlation of facilities per 100,000 with prevalence; permutation p.
#      Ecological and descriptive.

suppressWarnings(suppressPackageStartupMessages({
  library(spdep)
  library(sf)
  library(jsonlite)
}))

# Outputs are committed, so write LF line endings on every platform.
write_json_lf <- function(x, path) {
  con <- file(path, "wb")
  on.exit(close(con))
  writeLines(toJSON(x, auto_unbox = TRUE, pretty = TRUE, digits = 8, na = "null"), con, sep = "\n")
}

write_csv_lf <- function(x, path) {
  con <- file(path, "wb")
  on.exit(close(con))
  write.csv(x, con, row.names = FALSE)
}

pct <- function(p) sprintf("%.1f%%", 100 * p)
fmt_p <- function(p) if (p < 0.001) "< 0.001" else sprintf("= %.3f", p)

state_values <- function(direct, measure, age_group, codes) {
  rows <- direct[direct$measure == measure & direct$age_group == age_group, ]
  rows <- rows[match(codes, rows$geography), ]
  # `suppressed` is written by Python as "True"/"False".
  stopifnot(nrow(rows) == length(codes), !any(is.na(rows$estimate)), !any(toupper(as.character(rows$suppressed)) == "TRUE"))
  rows
}

neighbours <- function(spec, codes) {
  shapes <- st_read(spec$boundaries, quiet = TRUE)
  shapes <- shapes[match(codes, shapes[[spec$boundary_key]]), ]
  stopifnot(!any(is.na(shapes[[spec$boundary_key]])))
  snap <- if (is.null(spec$snap)) NULL else spec$snap
  nb <- poly2nb(shapes, queen = TRUE, snap = snap, row.names = codes)
  pairs <- matrix(spec$known_pairs, ncol = 2)
  pairs_ok <- vapply(seq_len(nrow(pairs)), function(i) {
    pairs[i, 2] %in% codes[nb[[match(pairs[i, 1], codes)]]]
  }, logical(1))
  checks <- list(
    snap = if (is.null(snap)) "default (sqrt of machine epsilon)" else snap,
    min_neighbours = min(card(nb)),
    max_neighbours = max(card(nb)),
    links = sum(card(nb)),
    symmetric = is.symmetric.nb(nb),
    known_pairs = lapply(seq_len(nrow(pairs)), function(i) {
      list(a = pairs[i, 1], b = pairs[i, 2], adjacent = pairs_ok[[i]])
    })
  )
  if (checks$min_neighbours < 1 || !checks$symmetric || !all(pairs_ok)) {
    stop("contiguity check failed: ", toJSON(checks, auto_unbox = TRUE))
  }
  list(nb = nb, checks = checks)
}

benjamini_hochberg <- function(p) p.adjust(p, method = "BH")

global_moran <- function(spec, direct, codes, lw) {
  rows <- lapply(seq_len(nrow(spec$moran_measures)), function(i) {
    m <- spec$moran_measures[i, ]
    d <- state_values(direct, m$measure, m$age_group, codes)
    set.seed(spec$seed)
    mc <- moran.mc(d$estimate, lw, nsim = spec$nsim, alternative = "greater")
    data.frame(
      measure = m$measure, age_group = m$age_group, role = m$role,
      moran_i = unname(mc$statistic), expected_i = -1 / (length(codes) - 1),
      p_perm = mc$p.value, nsim = spec$nsim,
      n_states = nrow(d),
      n_reliable = sum(d$precision_flag == "reliable"),
      n_review = sum(d$precision_flag == "review"),
      n_unreliable = sum(d$precision_flag == "unreliable"),
      n_zero_estimate = sum(d$estimate == 0),
      median_cv_nonzero = median(d$se[d$estimate > 0] / d$estimate[d$estimate > 0]),
      stringsAsFactors = FALSE
    )
  })
  out <- do.call(rbind, rows)
  out$p_bh <- benjamini_hochberg(out$p_perm)
  out
}

lisa <- function(spec, direct, codes, lw) {
  d <- state_values(direct, spec$lisa$measure, spec$lisa$age_group, codes)
  set.seed(spec$seed)
  lm <- localmoran_perm(d$estimate, lw, nsim = spec$nsim, alternative = "two.sided", iseed = spec$seed)
  p <- lm[, "Pr(z != E(Ii)) Sim"]
  quadrant <- as.character(attr(lm, "quadr")$mean)
  q <- benjamini_hochberg(p)
  labels <- c("High-High" = "High-High", "Low-Low" = "Low-Low", "High-Low" = "High-Low", "Low-High" = "Low-High")
  cls <- ifelse(q < spec$lisa$q, labels[quadrant], "Not significant")
  data.frame(
    geography = codes, measure = spec$lisa$measure, age_group = spec$lisa$age_group,
    estimate = d$estimate, precision_flag = d$precision_flag,
    local_i = lm[, "Ii"], p_perm = p, q_bh = q, quadrant = quadrant,
    lisa_class = unname(cls), exploratory = TRUE,
    stringsAsFactors = FALSE
  )
}

silhouette_mean <- function(D, cl) {
  D <- as.matrix(D)
  s <- vapply(seq_along(cl), function(i) {
    own <- cl == cl[i]
    if (sum(own) == 1) return(0)
    a <- mean(D[i, own & seq_along(cl) != i])
    b <- min(vapply(setdiff(unique(cl), cl[i]), function(k) mean(D[i, cl == k]), numeric(1)))
    (b - a) / max(a, b)
  }, numeric(1))
  mean(s)
}

profile_clusters <- function(spec, direct, codes) {
  X <- sapply(spec$domains, function(m) state_values(direct, m, spec$cluster_age_group, codes)$estimate)
  colnames(X) <- spec$domains
  Z <- scale(X)
  D <- dist(Z, method = "euclidean")
  tree <- hclust(D, method = "ward.D2")
  ks <- spec$k_range[1]:spec$k_range[2]
  sil <- data.frame(k = ks, mean_silhouette = vapply(ks, function(k) silhouette_mean(D, cutree(tree, k)), numeric(1)))
  # Highest mean silhouette; a tie (to 1e-12) goes to the smaller k.
  best <- sil$k[which(sil$mean_silhouette >= max(sil$mean_silhouette) - 1e-12)[1]]
  sil$chosen <- sil$k == best
  cl <- cutree(tree, best)
  # Number clusters by first appearance in state-code order, so labels are stable.
  cl <- match(cl, unique(cl))
  members <- data.frame(geography = codes, cluster = cl, X, stringsAsFactors = FALSE, check.names = FALSE)
  zcols <- as.data.frame(Z)
  names(zcols) <- paste0("z_", spec$domains)
  members <- cbind(members, zcols)
  profiles <- lapply(sort(unique(cl)), function(k) {
    idx <- cl == k
    list(
      cluster = k, n_states = sum(idx), states = codes[idx],
      mean_prevalence = as.list(colMeans(X[idx, , drop = FALSE])),
      mean_z = as.list(colMeans(Z[idx, , drop = FALSE]))
    )
  })
  list(members = members, silhouette = sil, k = best, profiles = profiles)
}

services <- function(spec, direct, codes) {
  fac <- read.csv(spec$facilities_csv, stringsAsFactors = FALSE)
  fac <- fac[match(codes, fac$state_code), ]
  stopifnot(nrow(fac) == length(codes), !any(is.na(fac$facilities_per_100k)))
  d <- state_values(direct, spec$services$measure, spec$services$age_group, codes)
  x <- fac$facilities_per_100k
  y <- d$estimate
  rho <- cor(rank(x), rank(y))
  set.seed(spec$seed)
  perm <- replicate(spec$nsim, cor(rank(x), rank(sample(y))))
  p <- (1 + sum(abs(perm) >= abs(rho) - 1e-12)) / (spec$nsim + 1)
  list(
    measure = spec$services$measure, age_group = spec$services$age_group,
    supply = "GRID3 NGA - Health Facilities v2.0, all facilities per 100,000 people (NBS 2023 population)",
    n_states = length(codes), spearman_rho = rho, p_perm_two_sided = p, nsim = spec$nsim, seed = spec$seed,
    facilities_total = sum(fac$facilities),
    facilities_per_100k = list(min = min(x), median = median(x), max = max(x),
      min_state = codes[which.min(x)], max_state = codes[which.max(x)]),
    caveats = c(
      "Ecological association between state averages: no causal claim and no inference about individuals.",
      "General health facilities are not disability services; the count says nothing about rehabilitation, assistive technology or accessibility.",
      "GRID3 v2.0 is non-exhaustive and not validated by government; private facilities in particular may be under-counted."
    )
  )
}

sentence_moran <- function(r, label, n_tests) {
  hedge <- if (r$n_review > 0) {
    sprintf(" %d of the 37 state estimates are flagged for review (few events), which pulls I towards 0, so a weak result is not evidence of no pattern.", r$n_review)
  } else {
    " All 37 state estimates are flagged reliable."
  }
  verdict <- if (r$p_bh < 0.05) "is geographically clustered" else "shows no clear geographic clustering"
  borderline <- if (r$p_perm < 0.05 && r$p_bh >= 0.05) {
    " The uncorrected p-value is below 0.05, but not after correcting for multiple tests."
  } else {
    ""
  }
  sprintf("%s %s across Nigeria's states (Moran's I = %.2f, permutation p %s; adjusted p %s across %d tests).%s%s",
    label, verdict, r$moran_i, fmt_p(r$p_perm), fmt_p(r$p_bh), n_tests, borderline, hedge)
}

main <- function(spec_path) {
  spec <- fromJSON(spec_path)
  direct <- read.csv(spec$outcome_csv, stringsAsFactors = FALSE)
  direct <- direct[direct$sex == "all" & direct$breakdown == "all", ]
  codes <- sort(unique(direct$geography))
  stopifnot(length(codes) == 37)

  # 1. Neighbours.
  nbr <- neighbours(spec, codes)
  lw <- nb2listw(nbr$nb, style = "W")
  edges <- do.call(rbind, lapply(seq_along(codes), function(i) {
    data.frame(geography = codes[i], neighbour = codes[nbr$nb[[i]]], weight = lw$weights[[i]], stringsAsFactors = FALSE)
  }))

  # 2. Global Moran's I.
  moran <- global_moran(spec, direct, codes, lw)

  # 3. LISA.
  local <- lisa(spec, direct, codes, lw)

  # 4. Profile clustering.
  clusters <- profile_clusters(spec, direct, codes)

  # 5. Services against needs.
  svc <- services(spec, direct, codes)

  dir.create(spec$out_dir, showWarnings = FALSE, recursive = TRUE)
  write_csv_lf(edges, file.path(spec$out_dir, "neighbours.csv"))
  write_csv_lf(moran, file.path(spec$out_dir, "moran_global.csv"))
  write_csv_lf(local, file.path(spec$out_dir, "lisa_disability3_18plus.csv"))
  write_csv_lf(clusters$members, file.path(spec$out_dir, "profile_clusters.csv"))
  write_csv_lf(clusters$silhouette, file.path(spec$out_dir, "profile_silhouette.csv"))
  write_json_lf(svc, file.path(spec$out_dir, "services_vs_need.json"))

  labels <- setNames(spec$moran_measures$label, paste(spec$moran_measures$measure, spec$moran_measures$age_group))
  moran_out <- lapply(seq_len(nrow(moran)), function(i) {
    r <- moran[i, ]
    c(as.list(r), sentence = sentence_moran(r, labels[[paste(r$measure, r$age_group)]], nrow(moran)))
  })
  sig <- local[local$lisa_class != "Not significant", ]
  lisa_sentence <- if (nrow(sig) == 0) {
    sprintf("Exploratory: no state is a significant local hotspot or coldspot of disability among adults 18+ after correcting for 37 tests (false discovery rate %.2f).", spec$lisa$q)
  } else {
    sprintf("Exploratory: after correcting for 37 tests (false discovery rate %.2f), %s. With 37 states this is a lead to look into, not a finding.",
      spec$lisa$q, paste(sprintf("%s is %s", sig$geography, sig$lisa_class), collapse = "; "))
  }
  group_text <- paste(vapply(clusters$profiles, function(g) {
    sprintf("group %d (%d states: %s) is above the state average in %d of 6 domains",
      g$cluster, g$n_states, paste(g$states, collapse = ", "), sum(unlist(g$mean_z) > 0))
  }, character(1)), collapse = "; ")
  cluster_sentence <- sprintf(
    "Descriptive only: grouping states by their six-domain disability profile (adults 18+) gives %d groups (Ward clustering, best mean silhouette %.2f of k = 2-6): %s. Many single-domain estimates are flagged for review, so the groups are rough and carry no inference.",
    clusters$k, max(clusters$silhouette$mean_silhouette), group_text)
  svc_sentence <- sprintf(
    "Ecological and descriptive: across the 37 states, health facilities per 100,000 people and adult disability prevalence have a Spearman correlation of %.2f (permutation p %s). This compares state averages only; it says nothing about individuals or causes, and general health facilities are not disability services.",
    svc$spearman_rho, fmt_p(svc$p_perm_two_sided))
  summary <- list(
    source = "DHS 2024 direct state estimates (data/public/aggregates/dhs2024_state.csv), sex = all, breakdown = all",
    note = "Fay-Herriot failed its pre-declared diagnostics (docs/verification.md D56); every result here uses the direct estimates. No spatial method is run on JONAPWD (D17).",
    seed = spec$seed, nsim = spec$nsim,
    neighbours = nbr$checks,
    moran = list(alternative = "greater (positive spatial autocorrelation)", multiple_testing = "Benjamini-Hochberg across the 8 tests",
      precision_note = "Noisy state estimates add independent error, which biases Moran's I towards 0; results for measures with many review-flagged states are conservative.",
      results = moran_out),
    lisa = list(exploratory = TRUE, measure = spec$lisa$measure, age_group = spec$lisa$age_group,
      alternative = "two-sided, conditional permutation", fdr_q = spec$lisa$q,
      classes = as.list(table(factor(local$lisa_class, levels = c("High-High", "Low-Low", "High-Low", "Low-High", "Not significant")))),
      significant_states = sig$geography, sentence = lisa_sentence),
    clusters = list(descriptive = TRUE, method = "Ward.D2 on Euclidean distance of standardised 18+ domain prevalences",
      k = clusters$k, silhouette = clusters$silhouette, profiles = clusters$profiles, sentence = cluster_sentence),
    services = c(svc, sentence = svc_sentence)
  )
  write_json_lf(summary, file.path(spec$out_dir, "summary.json"))
  cat("spatial: wrote", length(codes), "states;", nrow(moran), "Moran tests; k =", clusters$k, "\n")
}

args <- commandArgs(trailingOnly = TRUE)
if (length(args) != 1) stop("usage: Rscript spatial.R <spec.json>")
main(args[[1]])
