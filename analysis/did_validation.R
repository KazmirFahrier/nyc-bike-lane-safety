# Independent validation of the Python difference-in-differences, plus the
# negative binomial outcome model.
#
# Two jobs, and the first one matters more than it looks.
#
# 1. RE-ESTIMATE THE GROUP-TIME ATTs FROM SCRATCH. This is deliberately not a
#    port of analysis/did.py -- it is written from the estimator's definition,
#    in a different language, by a different route (data.table joins rather
#    than pandas reindexing). If the two agree to numerical tolerance, the
#    Python implementation is not carrying a silent indexing bug, which is the
#    most common way a hand-rolled Callaway-Sant'Anna goes wrong.
#
# 2. FIT THE NEGATIVE BINOMIAL. MASS::glm.nb estimates the dispersion
#    parameter by maximum likelihood rather than taking it as given, which is
#    what the corridor panel needs: variance/mean is 6.5, far outside Poisson.
#    The exposure offset enters as log(segments) + log(citywide ridership), so
#    the coefficient on treatment reads as a change in injuries per segment per
#    unit of ridership rather than a change in raw counts.
#
# Usage:  Rscript analysis/did_validation.R

suppressPackageStartupMessages({
  library(data.table)
  library(MASS)
  library(ggplot2)
})

# Run from the project root (the Makefile does). Walk up if invoked elsewhere.
root <- "."
for (i in 1:4) {
  if (dir.exists(file.path(root, "data", "interim"))) break
  root <- file.path(root, "..")
}
if (!dir.exists(file.path(root, "data", "interim")))
  stop("run from the project root: Rscript analysis/did_validation.R")

panel   <- fread(file.path(root, "data/interim/corridor_panel.csv"))
matched <- fread(file.path(root, "data/interim/matched_corridors.csv"))

panel[, ips := cyclist_injured / n_segments]

# ---- 1. group-time ATTs, from the definition -------------------------------
att_rows <- list()
for (g in sort(unique(matched$cohort_year))) {
  mg   <- matched[cohort_year == g]
  base <- g - 1L

  treated <- mg[is_treated_here == TRUE]
  ctrl0   <- mg[is_treated_here == FALSE]

  # not-yet-treated controls only: a corridor stops being a control once its
  # own lane goes in
  firsts <- unique(panel[, .(corridor_id, first_protected_year)])
  ctrl0  <- merge(ctrl0, firsts, by = "corridor_id", all.x = TRUE)

  ybase <- panel[panel_year == base, .(corridor_id, y_base = ips)]

  for (t in sort(unique(panel$panel_year))) {
    if (t == base) next
    yt <- panel[panel_year == t, .(corridor_id, y_t = ips)]

    wmean_diff <- function(units) {
      d <- merge(merge(units, yt, by = "corridor_id"), ybase, by = "corridor_id")
      d <- d[!is.na(y_t) & !is.na(y_base)]
      if (nrow(d) == 0L || sum(d$cem_weight) == 0) return(NA_real_)
      sum((d$y_t - d$y_base) * d$cem_weight) / sum(d$cem_weight)
    }

    ctrl <- ctrl0[is.na(first_protected_year) | first_protected_year > max(t, g)]
    if (nrow(ctrl) == 0L) next

    dt_ <- wmean_diff(treated)
    dc_ <- wmean_diff(ctrl)
    if (is.na(dt_) || is.na(dc_)) next

    att_rows[[length(att_rows) + 1L]] <- data.table(
      cohort = g, year = t, event_time = t - g,
      att = dt_ - dc_, n_treated = nrow(treated)
    )
  }
}
att <- rbindlist(att_rows)

# ---- compare against the Python implementation -----------------------------
py_path <- file.path(root, "analysis/output/att_gt.csv")
if (file.exists(py_path)) {
  py <- fread(py_path)
  cmp <- merge(att, py[, .(cohort, year, att_py = att)], by = c("cohort", "year"))
  cmp[, delta := abs(att - att_py)]
  cat("\n=== CROSS-IMPLEMENTATION CHECK (R vs Python) ===\n")
  cat(sprintf("  group-time ATTs compared : %d\n", nrow(cmp)))
  cat(sprintf("  max absolute difference  : %.3e\n", max(cmp$delta)))
  cat(sprintf("  %s\n", if (max(cmp$delta) < 1e-9)
      "IDENTICAL to numerical tolerance -- implementations agree" else
      "DIFFER -- investigate before trusting either"))
} else {
  cat("\n(no Python att_gt.csv found; run analysis/did.py first)\n")
}

# ---- event-study figure ----------------------------------------------------
ev <- att[event_time %between% c(-5, 5),
          .(att = weighted.mean(att, n_treated)), by = event_time][order(event_time)]

p <- ggplot(ev, aes(event_time, att)) +
  geom_hline(yintercept = 0, colour = "grey40") +
  geom_vline(xintercept = -0.5, linetype = "dashed", colour = "grey60") +
  geom_line(colour = "#1f4e79") +
  geom_point(colour = "#1f4e79", size = 2) +
  labs(
    title = "Cyclist injuries around protected lane installation",
    subtitle = "Group-time ATT by years since install; base period is the year before",
    x = "Years since protected lane installed",
    y = "Injuries per segment-year, vs matched controls"
  ) +
  theme_minimal(base_size = 11)
dir.create(file.path(root, "analysis/output"), showWarnings = FALSE)
ggsave(file.path(root, "analysis/output/event_study_R.png"), p,
       width = 7, height = 4.5, dpi = 150)

# ---- 2. negative binomial with exposure offset -----------------------------
units <- unique(matched[, .(corridor_id, cem_weight)], by = "corridor_id")
d <- merge(panel, units, by = "corridor_id")
d[, treated_now := as.integer(!is.na(first_protected_year) &
                              panel_year >= first_protected_year)]
d <- d[has_exposure == TRUE & n_segments > 0]
d[, `:=`(offset_term = log_segments + log_exposure,
         yr = factor(panel_year), boro = factor(boro_code))]

# NOTE ON WHAT THIS MODEL IS AND IS NOT.
# This fits the CEM-matched, weighted sample with year and borough effects but
# *no corridor fixed effects*. It therefore compares corridors that have lanes
# against corridors that do not, and DOT does not pick corridors at random --
# it installs where cyclists are already being hurt. The coefficient is a
# cross-sectional association and must not be read as the effect of a lane.
# The within-corridor estimates, which difference that selection out, are in
# analysis/count_models.py (Poisson PML with corridor + year fixed effects and
# corridor-clustered standard errors). glm.nb is used here because it estimates
# the dispersion by maximum likelihood, which is the right check on whether the
# overdispersion is as severe as the raw variance/mean suggests.
cat("\n=== NEGATIVE BINOMIAL (MASS::glm.nb) -- ASSOCIATION, NOT EFFECT ===\n")
cat(sprintf("  sample: CEM-matched corridors, weighted; no corridor fixed effects\n"))
cat(sprintf("  corridor-years: %d\n", nrow(d)))
fit <- tryCatch(
  glm.nb(cyclist_injured ~ treated_now + yr + boro + offset(offset_term),
         data = d, weights = cem_weight),
  error = function(e) { cat("  glm.nb failed:", conditionMessage(e), "\n"); NULL }
)
if (!is.null(fit)) {
  s <- summary(fit)
  co <- s$coefficients["treated_now", ]
  cat(sprintf("  theta (dispersion)  : %.3f  (Poisson would be Inf)\n", fit$theta))
  cat(sprintf("  treated_now coef    : %+.4f  (SE %.4f, p = %.3f)\n",
              co[1], co[2], co[4]))
  cat(sprintf("  incidence rate ratio: %.3f  [%.3f, %.3f]\n",
              exp(co[1]), exp(co[1] - 1.96 * co[2]), exp(co[1] + 1.96 * co[2])))
  cat(sprintf("  => %+.1f%% change in cyclist injuries per segment, per unit ridership\n",
              100 * (exp(co[1]) - 1)))
}
cat("\nwrote analysis/output/event_study_R.png\n")
