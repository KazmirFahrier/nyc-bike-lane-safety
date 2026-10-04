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
# This validates estimator arithmetic. It does not validate causal identification.
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

    keys <- c("boro_code", "injury_bin")
    nt <- treated[, .(nt=.N), by=keys]
    nc <- ctrl[, .(nc=.N), by=keys]
    support <- merge(nt, nc, by=keys)
    treated_cell <- merge(treated, support[, ..keys], by=keys)
    ctrl <- merge(ctrl, support, by=keys)
    ctrl[, cem_weight := nt / nc]
    dt_ <- wmean_diff(treated_cell)
    dc_ <- wmean_diff(ctrl)
    if (is.na(dt_) || is.na(dc_)) next

    att_rows[[length(att_rows) + 1L]] <- data.table(
      cohort = g, year = t, event_time = t - g,
      att = dt_ - dc_, n_treated = nrow(treated_cell)
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
  fwrite(cmp, file.path(root, "analysis/output/r_validation.csv"))
  stopifnot(nrow(cmp) == nrow(att), nrow(cmp) == nrow(py), max(cmp$delta) < 1e-9)
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

cat("\nwrote analysis/output/event_study_R.png\n")
