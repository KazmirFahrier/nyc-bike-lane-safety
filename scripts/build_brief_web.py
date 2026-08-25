"""Render the policy brief as a self-contained web page.

Same argument as the PDF, different medium. The one thing the web version does
that the PDF cannot is render the three competing estimates as aligned
confidence intervals against a shared zero line, so a reader sees the
disagreement spatially before reading a number.

Figures are embedded as data URIs -- the artifact CSP blocks external hosts.

Usage:
    python scripts/build_brief_web.py
"""

from __future__ import annotations

import base64
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FIG = ROOT / "analysis" / "output"
OUT = ROOT / "docs" / "brief" / "brief_web.html"

# Scale for the interval chart: covers every confidence bound with a little air.
LO, HI = -60.0, 40.0
def pos(v: float) -> float:
    return 100.0 * (v - LO) / (HI - LO)

ESTIMATES = [
    ("Compared to the year before installation",
     "Callaway–Sant'Anna, base = last pre-treatment year",
     -17.7, -57.3, 20.2, True),
    ("Compared to the earlier pre-installation years",
     "Callaway–Sant'Anna, base = four years before that",
     8.0, -16.6, 34.7, False),
    ("Compared within each corridor, before vs after",
     "Poisson fixed effects, CEM-matched, corridor-clustered",
     12.1, -4.3, 31.3, False),
]


def img(name: str) -> str:
    b = (FIG / name).read_bytes()
    return "data:image/png;base64," + base64.b64encode(b).decode()


def interval_rows() -> str:
    out = []
    for label, method, est, lo, hi, is_first in ESTIMATES:
        out.append(f"""
      <div class="est{' est--anchor' if is_first else ''}">
        <div class="est__label">
          <span class="est__name">{label}</span>
          <span class="est__method">{method}</span>
        </div>
        <div class="est__track" role="img"
             aria-label="{est:+.1f} percent, 95 percent interval {lo:+.1f} to {hi:+.1f}">
          <span class="est__zero" style="left:{pos(0):.2f}%"></span>
          <span class="est__ci" style="left:{pos(lo):.2f}%;width:{pos(hi)-pos(lo):.2f}%"></span>
          <span class="est__dot" style="left:{pos(est):.2f}%"></span>
        </div>
        <div class="est__value">{est:+.1f}%</div>
      </div>""")
    return "".join(out)


HTML = f"""<title>Did NYC's Protected Bike Lanes Work?</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Newsreader:ital,opsz,wght@0,6..72,300..700;1,6..72,300..600&family=Public+Sans:wght@400;500;600;700&family=IBM+Plex+Mono:wght@400;500&display=swap">
<style>
:root {{
  --ground:#f7f8fa; --surface:#ffffff; --surface-2:#eef1f5;
  --ink:#12161c; --ink-2:#4a5460; --ink-3:#78838f;
  --rule:#dfe3e8; --rule-strong:#c3cad3;
  --accent:#0b5394; --accent-soft:#e8eef6;
  --warn:#b45309; --warn-soft:#fbf0e2;
  --serif:"Newsreader",Georgia,"Times New Roman",serif;
  --sans:"Public Sans",-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;
  --mono:"IBM Plex Mono",ui-monospace,Menlo,monospace;
  --measure:66ch;
}}
@media (prefers-color-scheme: dark) {{
  :root:not([data-theme="light"]) {{
    --ground:#0f131a; --surface:#161c25; --surface-2:#1c2430;
    --ink:#e9edf2; --ink-2:#a4afbb; --ink-3:#7d8794;
    --rule:#262e39; --rule-strong:#39434f;
    --accent:#6ea9e6; --accent-soft:#152538;
    --warn:#dda23f; --warn-soft:#2a2114;
  }}
}}
:root[data-theme="dark"] {{
  --ground:#0f131a; --surface:#161c25; --surface-2:#1c2430;
  --ink:#e9edf2; --ink-2:#a4afbb; --ink-3:#7d8794;
  --rule:#262e39; --rule-strong:#39434f;
  --accent:#6ea9e6; --accent-soft:#152538;
  --warn:#dda23f; --warn-soft:#2a2114;
}}

*,*::before,*::after {{ box-sizing:border-box; }}
body {{
  margin:0; background:var(--ground); color:var(--ink);
  font-family:var(--serif); font-size:1.0625rem; line-height:1.62;
  font-optical-sizing:auto;
  -webkit-font-smoothing:antialiased;
}}
.wrap {{ max-width:var(--measure); margin:0 auto; padding:0 1.5rem; }}
.wide {{ max-width:min(52rem,100% - 3rem); margin-inline:auto; }}

/* ---- masthead ---- */
header.mast {{ border-bottom:2px solid var(--accent); margin-bottom:2.5rem; }}
.mast__inner {{ padding:4rem 1.5rem 2rem; max-width:var(--measure); margin:0 auto; }}
.eyebrow {{
  font-family:var(--sans); font-size:.6875rem; font-weight:600;
  letter-spacing:.14em; text-transform:uppercase; color:var(--accent);
  margin:0 0 1rem;
}}
h1 {{
  font-family:var(--serif); font-weight:600; font-size:clamp(2rem,5.2vw,3rem);
  line-height:1.1; letter-spacing:-.02em; margin:0 0 .75rem; text-wrap:balance;
}}
.standfirst {{
  font-size:1.1875rem; line-height:1.5; color:var(--ink-2);
  font-style:italic; margin:0 0 1.75rem; text-wrap:pretty;
}}
.byline {{
  font-family:var(--sans); font-size:.8125rem; line-height:1.6;
  color:var(--ink-3); display:flex; flex-wrap:wrap; gap:.4rem 1rem;
  padding-top:1.25rem; border-top:1px solid var(--rule);
}}
.byline strong {{ color:var(--ink-2); font-weight:600; }}
.independence {{
  font-family:var(--sans); font-size:.75rem; line-height:1.55; color:var(--ink-3);
  margin:1rem 0 0; max-width:60ch; font-style:normal;
}}
.byline code {{ font-family:var(--mono); font-size:.75rem; }}

/* ---- text ---- */
main {{ padding-bottom:5rem; }}
h2 {{
  font-family:var(--serif); font-weight:600; font-size:1.5rem; line-height:1.25;
  letter-spacing:-.01em; margin:3.25rem 0 .875rem; text-wrap:balance;
}}
h3 {{
  font-family:var(--sans); font-weight:600; font-size:.9375rem;
  letter-spacing:.01em; margin:2rem 0 .5rem; color:var(--ink);
}}
p {{ margin:0 0 1.1rem; }}
strong {{ font-weight:600; }}
a {{ color:var(--accent); text-decoration-thickness:1px; text-underline-offset:2px; }}
code {{ font-family:var(--mono); font-size:.8em; background:var(--surface-2);
        padding:.1em .35em; border-radius:3px; }}
.lede {{ font-size:1.1875rem; line-height:1.55; }}
hr {{ border:0; border-top:1px solid var(--rule); margin:3rem 0; }}

.callout {{
  background:var(--surface); border-left:3px solid var(--accent);
  padding:1.25rem 1.5rem; margin:1.75rem 0; border-radius:0 4px 4px 0;
  box-shadow:0 1px 2px rgba(18,22,28,.04);
}}
.callout p:last-child {{ margin-bottom:0; }}
.callout--warn {{ border-left-color:var(--warn); }}

/* ---- the interval comparison ---- */
.estimates {{
  margin:2rem auto 2.5rem; display:flex; flex-direction:column; gap:0;
  background:var(--surface); border:1px solid var(--rule); border-radius:6px;
  overflow:hidden;
}}
.estimates__head, .estimates__foot {{
  font-family:var(--sans); font-size:.6875rem; font-weight:600;
  letter-spacing:.1em; text-transform:uppercase; color:var(--ink-3);
  padding:.875rem 1.25rem; background:var(--surface-2);
}}
.estimates__foot {{
  text-transform:none; letter-spacing:0; font-weight:400; font-size:.8125rem;
  font-family:var(--serif); color:var(--ink-2); line-height:1.5;
  border-top:1px solid var(--rule);
}}
.est {{
  display:grid; grid-template-columns:minmax(0,1fr) minmax(9rem,1.1fr) auto;
  gap:1rem; align-items:center; padding:1rem 1.25rem;
  border-top:1px solid var(--rule);
}}
.est--anchor {{ background:var(--warn-soft); }}
.est__label {{ display:flex; flex-direction:column; gap:.15rem; min-width:0; }}
.est__name {{ font-size:.9375rem; line-height:1.35; }}
.est__method {{
  font-family:var(--sans); font-size:.6875rem; color:var(--ink-3);
  line-height:1.4;
}}
.est__track {{ position:relative; height:1.5rem; }}
.est__zero {{
  position:absolute; top:0; bottom:0; width:1px; background:var(--rule-strong);
  transform:translateX(-.5px);
}}
.est__ci {{
  position:absolute; top:50%; height:3px; border-radius:2px;
  background:var(--accent); opacity:.28; transform:translateY(-50%);
}}
.est--anchor .est__ci {{ background:var(--warn); }}
.est__dot {{
  position:absolute; top:50%; width:10px; height:10px; border-radius:50%;
  background:var(--accent); transform:translate(-50%,-50%);
  box-shadow:0 0 0 2px var(--surface);
}}
.est--anchor .est__dot {{ background:var(--warn); box-shadow:0 0 0 2px var(--warn-soft); }}
.est__value {{
  font-family:var(--mono); font-size:.9375rem; font-weight:500;
  font-variant-numeric:tabular-nums; text-align:right; min-width:4.5rem;
}}
@media (max-width:34rem) {{
  .est {{ grid-template-columns:1fr auto; }}
  .est__track {{ grid-column:1 / -1; }}
}}

/* ---- figures ---- */
figure {{ margin:2.5rem 0; }}
figure img {{
  width:100%; height:auto; display:block; border-radius:5px;
  border:1px solid var(--rule); background:#fff;
}}
figcaption {{
  font-family:var(--sans); font-size:.75rem; line-height:1.55;
  color:var(--ink-3); margin-top:.75rem; max-width:56ch;
}}

/* ---- findings list ---- */
.findings {{ counter-reset:f; list-style:none; padding:0; margin:1.5rem 0; }}
.findings > li {{
  counter-increment:f; position:relative; padding-left:2.5rem;
  margin-bottom:1.5rem;
}}
.findings > li::before {{
  content:counter(f,decimal-leading-zero); position:absolute; left:0; top:.15em;
  font-family:var(--mono); font-size:.8125rem; color:var(--accent);
  font-variant-numeric:tabular-nums;
}}
.findings ul {{ margin:.6rem 0 0; padding-left:1.1rem; }}
.findings li li {{ margin-bottom:.5rem; }}

/* ---- verification table ---- */
.tablewrap {{ overflow-x:auto; margin:1.5rem 0 2rem; }}
table {{ border-collapse:collapse; width:100%; font-size:.9375rem; }}
th {{
  font-family:var(--sans); font-size:.6875rem; font-weight:600;
  letter-spacing:.1em; text-transform:uppercase; color:var(--ink-3);
  text-align:left; padding:0 1rem .6rem 0; border-bottom:1px solid var(--rule-strong);
  white-space:nowrap;
}}
td {{ padding:.7rem 1rem .7rem 0; border-bottom:1px solid var(--rule);
      vertical-align:top; }}
td:last-child, th:last-child {{ padding-right:0; }}
.num {{ font-family:var(--mono); font-variant-numeric:tabular-nums;
        white-space:nowrap; }}

footer {{
  border-top:1px solid var(--rule); margin-top:4rem; padding:2rem 0 0;
  font-family:var(--sans); font-size:.8125rem; color:var(--ink-3); line-height:1.6;
}}
@media (prefers-reduced-motion:reduce) {{ *{{animation:none!important;transition:none!important}} }}
</style>

<header class="mast">
  <div class="mast__inner">
    <p class="eyebrow">Independent analysis · NYC open data</p>
    <h1>Did New York's protected bike lanes make cycling safer?</h1>
    <p class="standfirst">Twelve years of city data, and a straight answer about why
      they cannot settle it.</p>
    <div class="byline">
      <span><strong>Kazmir Fahrier</strong></span>
      <span>August 2026</span>
      <span>57,353 crashes · 4,357 lane segments · 6.2M counter readings</span>
      <span><code>github.com/KazmirFahrier/nyc-bike-lane-safety</code></span>
    </div>
    <p class="independence">Independent analysis by a private individual, written on my own
      initiative using public data. Not affiliated with, commissioned by, endorsed by, or
      speaking for the New York City Department of Transportation, the Vision Zero program,
      or any government agency or organization.</p>
  </div>
</header>

<main>
<div class="wrap">

<h2>The short version</h2>

<p class="lede">Between 2013 and 2024 the Department of Transportation installed
protected bike lanes on 4,357 street segments — 519 distinct corridors. This
analysis asked whether cyclist injuries fell on those corridors relative to
comparable corridors that did not get lanes.</p>

<div class="callout">
<p><strong>The answer is that the question cannot be settled with this data, and
the reason is worth knowing.</strong></p>
</div>

<p>DOT does not install protected lanes at random. It installs them where cyclists
are already being hurt. Corridors that received a protected lane saw their
cyclist-injury rate <strong>rise 55% over the five years before installation</strong>,
while matched comparison corridors stayed flat. By the year the lane went in,
treated corridors were running injury rates a third higher than the corridors they
most resemble.</p>

<p>That is good government. It is also fatal to the standard evaluation method. When
a program is targeted at a problem that has just spiked, the problem tends to subside
afterward whether or not the program works — and the standard method cannot tell the
two apart.</p>

<p>The consequence is concrete. Three defensible analytic choices give three different
answers, and they do not agree on the direction:</p>

</div>

<div class="wide">
  <div class="estimates">
    <div class="estimates__head">Estimated change in cyclist injuries · 95% interval</div>
    {interval_rows()}
    <div class="estimates__foot">None is statistically distinguishable from no change.
      The highlighted row is the conventional choice — and it is the one anchored on
      the year treated corridors' injuries peaked.</div>
  </div>
</div>

<div class="wrap">

<p>The difference between the first row and the other two is not a finding about bike
lanes. It is a finding about which year you choose as the point of comparison — and
treated corridors' injuries peak in exactly the year the first row uses.</p>

<div class="callout callout--warn">
<p><strong>None of this is evidence that protected lanes are ineffective or harmful.</strong>
The honest statement is narrower and more useful: the observational record of NYC's
protected lane program does not support a credible estimate of its safety effect, and
any published figure that does not address the targeting problem should be treated with
suspicion — <em>including figures that flatter the program</em>.</p>
</div>

<hr>

<h2>Why this is hard</h2>

<p>The intuitive comparison — injuries on lanes versus injuries elsewhere — is wrong in
a way that is easy to state. Protected lanes go on busy, dangerous corridors. Those
corridors would have more cyclist injuries than quiet residential streets whether or not
they had lanes. Comparing them directly measures where the lanes are, not what they do.</p>

<p>This analysis addresses it the standard way: every treated corridor is compared only
against corridors <strong>in the same borough, with a similar recent injury history</strong>, in
the same years. This is coarsened exact matching, and it works — before matching,
Manhattan's treated corridors were running 4.04 pre-period injuries against 2.95 on
untreated corridors; after matching, 4.04 against 3.93.</p>

<p>Matching also revealed something a citywide average conceals.
<strong>Selection runs in opposite directions in different boroughs.</strong> In
Manhattan, DOT put lanes on corridors more dangerous than average. In the Bronx, it put
them on corridors <em>safer</em> than average (1.17 versus 1.72 pre-period injuries). A
single citywide comparison nets these against each other and appears unbiased while being
wrong in both boroughs.</p>

<p>But matching on the <em>level</em> of past injuries does not fix matching on the
<em>trend</em>. That is the problem that remains, and it is the one that matters.</p>

</div>

<div class="wide">
<figure>
  <img src="{img('raw_trends.png')}" alt="Cyclist injuries per segment-year for treated corridors versus matched comparison corridors, aligned on years since installation. Treated corridors start lower, rise sharply to a peak the year before installation, then climb above controls.">
  <figcaption>Weighted mean cyclist injuries per segment-year, 472 treated corridors
    against their CEM-matched comparison corridors, aligned on years since installation.
    Sources: NYPD Motor Vehicle Collisions, NYC DOT Bike Routes.</figcaption>
</figure>
</div>

<div class="wrap">

<p>Read the chart from the left. Five years before installation, corridors that would
later receive a protected lane were <strong>safer</strong> than their eventual comparison
group — 0.076 cyclist injuries per segment-year against 0.090. Over the next four years
they deteriorated sharply, peaking at 0.119 the year before the lane arrived. The
comparison corridors barely moved across the same period.</p>

<p>This is the signature of a well-targeted program, and it is also the signature of a
question that observational data cannot answer. The corridors were selected
<em>because</em> they were getting worse.</p>

<hr>

<h2>What the analysis found</h2>

<h3>The estimate depends on an arbitrary choice</h3>

<p>The standard method compares outcomes after treatment to the year immediately before
it. Applied here, that means comparing against the worst year those corridors had — the
spike that triggered the intervention. Using a different but equally defensible reference
period, the four years before that spike, the estimated effect reverses sign, from −17.7%
to +8.0%.</p>

<p>An effect estimate that flips direction depending on which pre-treatment year you
anchor to is not an effect estimate. It is a measurement of the spike.</p>

</div>

<div class="wide">
<figure>
  <img src="{img('event_study.png')}" alt="Event study of group-time average treatment effects by years since installation. Post-installation estimates occupy the same range as pre-installation ones, with no visible break at treatment.">
  <figcaption>Callaway–Sant'Anna group-time average treatment effects by years since
    installation, with 95% confidence intervals from a 1,000-replication corridor-level
    block bootstrap. The year before installation is the reference and is not plotted.</figcaption>
</figure>
</div>

<div class="wrap">

<p>If protected lanes changed cyclist safety, a visible break at installation would be
expected — estimates sitting at one level before and a different level after. They do
not. The post-installation estimates occupy the same range as the pre-installation ones.
Whatever was happening on these corridors before the lane continued afterward.</p>

<h3>A methodological point for anyone evaluating a phased rollout</h3>

<p>The most common statistical method for this kind of rollout, two-way fixed effects,
gives <strong>+21.2%</strong> here — a substantially different number from the estimator
designed for staggered adoption (−17.7% on the same base period). When a program is rolled
out over many years and its effects vary over time, two-way fixed effects uses
already-treated units as comparisons for later-treated ones, and can return the wrong sign
even when every underlying effect points the same way. Agencies evaluating phased
rollouts — and that is most of them — should know that this method, still the default in a
great deal of published work, is not reliable in this setting.</p>

<hr>

<h2>What the data <em>do</em> establish</h2>

<p>Four findings are solid, do not depend on the contested causal question, and are
directly actionable.</p>

<ol class="findings">
<li><strong>Cycling in New York grew 44.5% between 2014 and 2024</strong>, measured from
DOT's own automated counters on a like-for-like basis. Growth was not steady: the largest
single-year jump was <strong>+22.2% in 2020</strong>. Any assessment of cyclist safety
that reports injury counts without this denominator is misleading — injuries can rise
while risk per rider falls.</li>

<li><strong>Crash geocoding quality varies enough to affect analysis.</strong> 7.5% of
cyclist-injury crash records cannot be placed on a map; 217 records place the crash at
latitude 0, in the Gulf of Guinea. The rate is not stable over time: 86.3% of 2016 records
geocoded successfully against 94.8% in 2023. Any year-over-year corridor comparison
inherits that swing.</li>

<li><strong>The bike route file needs three corrections before it can be used for
evaluation.</strong> These are not criticisms of a file built for a different purpose, but
they are traps:
  <ul>
    <li><strong>"Protected" covers two different things.</strong> 5,220 records are
    on-street protected lanes; 3,215 are greenway and park paths carrying the identical
    label. They are different interventions, with different rider populations and no
    adjacent motor traffic. Treating them as one credits street redesign with greenway
    safety.</li>
    <li><strong>403 "protected" segments carry installation dates before 1990</strong> —
    1894, 1900, 1909 — inherited from the underlying street centerline rather than from any
    bike facility.</li>
    <li><strong>439 protected segments are retired with no recorded end date.</strong> A
    corridor that gained a lane and later lost it is not treated for the whole period, and
    the file does not say when it stopped.</li>
  </ul>
</li>

<li><strong>Two bridge counters are double-counted.</strong> "Manhattan Bridge Display Bike
Counter" and "Manhattan Bridge Bike Comprehensive" report identical daily totals on 2,338
days from the same coordinates; the Brooklyn Bridge has the same duplication. Summing all
counters overstates the two busiest cycling crossings in the city.</li>
</ol>

<hr>

<h2>What would actually answer the question</h2>

<p>The obstacle is not data volume. It is that installation timing is driven by the outcome
being measured. Four routes past it, in rough order of cost:</p>

<h3>Use DOT's own project pipeline records</h3>
<p>Corridors that were <em>proposed</em> for a protected lane but not built — because of
community board opposition, a competing capital project, or budget timing — are the
comparison group this analysis needs. They were selected by the same process, at the same
point in their injury history, and did not receive treatment. This is the single
highest-value addition, and the records exist inside DOT.</p>

<h3>Exploit installation delays</h3>
<p>Where a corridor's construction was postponed for reasons unrelated to its safety
record, the delay creates precisely the variation needed. Same corridors, same selection,
different timing.</p>

<h3>Measure ridership where the lanes are</h3>
<p>The city has 41 automated counters. They cannot measure ridership on 4,357 treated
segments, so this study models corridor-level exposure rather than measuring it — the
weakest link in the design, and the reason the per-rider question stays open. Counters on a
sample of treated and matched untreated corridors, installed <em>before</em> construction,
would close it.</p>

<h3>Record intended installation dates prospectively</h3>
<p>Much of the reconstruction difficulty here — undated removals, centerline dates standing
in for facility dates — would disappear if the treatment date and the removal date were
recorded as a matter of course.</p>

<hr>

<h2>How this was done</h2>

<p><strong>Data.</strong> NYPD Motor Vehicle Collisions (<code>h9gi-nx95</code>), 57,353
crashes involving a cyclist injury or fatality, 2013–2024. NYC DOT Bike Routes
(<code>mzxg-pwib</code>), 29,695 segment records. DOT automated bicycle counters
(<code>uczf-rk3c</code>), 6.2 million 15-minute readings across 41 sites. All public, all
free.</p>

<p><strong>Unit of analysis.</strong> Corridors, not blocks: maximal contiguous runs of
same-street, same-borough segments sharing one treatment history. DOT installs lanes on
corridors rather than blocks, and 92.5% of individual segment-years contain zero cyclist
injuries, which is too sparse to model. Aggregation gives 2,234 corridors and reduces
zero-outcome observations to 68.4%.</p>

<p><strong>Assigning crashes to corridors.</strong> NYPD geocodes crashes onto the street
centerline, and street segments meet end-to-end at intersections, so 92% of crashes sit
within one foot of two or more centerlines. Ties are broken on the street NYPD
independently reports; where the tied segments still disagree about treatment status —
3,911 crashes, 13.4% — the crash is flagged and excluded from the main analysis rather than
assigned arbitrarily.</p>

<p><strong>Estimation.</strong> Callaway–Sant'Anna group-time average treatment effects for
the staggered rollout, with corridor-level block bootstrap inference (1,000 replications).
Poisson pseudo-maximum-likelihood with corridor and year fixed effects and
corridor-clustered standard errors for the within-corridor estimates — Poisson rather than
negative binomial because it stays consistent under the overdispersion present here
(variance-to-mean ratio 6.5) without the incidental-parameters problem that affects negative
binomial with thousands of fixed effects.</p>

<h3>Verification</h3>
<p>A result nobody can reproduce is a claim, not a finding.</p>

<div class="tablewrap">
<table>
<thead><tr><th>Check</th><th>Result</th></tr></thead>
<tbody>
<tr><td>Estimator implemented twice — once in Python, once written independently in R from
the estimator's definition</td><td class="num">agree to 1 part in 10<sup>15</sup></td></tr>
<tr><td>Corridor construction built twice — DuckDB graph components, and PostGIS
<code>ST_ClusterDBSCAN</code></td><td class="num">identical partition,<br>20,439 segments</td></tr>
<tr><td>Automated pipeline tests, including end-to-end injury conservation</td>
<td class="num">39 passing</td></tr>
<tr><td>Every data pull, reconciled against the source's own row count</td>
<td class="num">short pull raises</td></tr>
</tbody>
</table>
</div>

<hr>

<h2>Limitations</h2>

<p>This analysis cannot say whether protected lanes are effective. It establishes that the
observational record does not support a credible answer, and why.</p>

<p>It also cannot speak to whether lanes caused ridership to rise, which would mean the
per-rider safety gain is understated here; to unreported crashes, since NYPD records only
what is reported; to near-misses, comfort, or whether people feel safe enough to ride; or
to the effect of any particular corridor's lane, since all estimates are averages.</p>

<p>The equity question this analysis set out to answer — whether protected lanes were
distributed evenly across neighborhoods, and whether any safety gains were — is not
addressed here and remains open.</p>

<footer>
<p>Independent analysis of public data by a private individual. Not affiliated with,
endorsed by, or produced for any government agency or organization. Findings and any errors
are my own. Code, data pipeline and full reproduction instructions at
<code>github.com/KazmirFahrier/nyc-bike-lane-safety</code>.</p>
</footer>

</div>
</main>
"""

# Escape every non-ASCII character to a numeric entity.
#
# The page is published as a bare fragment that a host wraps in its own
# <head>, so this file cannot declare its own charset -- and served without
# one, a browser falls back to Latin-1 and renders every em dash as "a€"" and
# every middot as "A·". Entities render identically under any encoding, so the
# document stops depending on a declaration it is not allowed to make.
ascii_html = HTML.encode("ascii", "xmlcharrefreplace").decode("ascii")

OUT.write_text(ascii_html, encoding="ascii")
n_escaped = sum(1 for a, b in zip(HTML, HTML) if ord(a) > 127)
print(f"wrote {OUT.relative_to(ROOT)} ({OUT.stat().st_size/1024:,.0f} KB, "
      f"{n_escaped} non-ASCII characters escaped)")
