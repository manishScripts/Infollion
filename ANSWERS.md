# Onboarding Experiment Investigation

Everything below comes from `analyze.py`, which uses only the Python standard library. To reproduce:

```
python3 analyze.py experiment_results.csv
```

Before running any comparison I checked the file for the usual problems. 14,000 rows, no duplicate
`user_id`s, no blank fields, `converted` is only ever 0 or 1, `variant` only ever `control` or
`treatment`, and exactly 5 segments. Nothing needed cleaning, so every number below uses all 14,000
rows with no exclusions.

Short version of what I found: the +6.61 pp topline is mostly an artifact of how users were assigned
to the two groups. Correcting for that brings the lift down to +1.63 pp, and nearly all of what
remains comes from a single segment.

---

## Q1. Overall (naive) difference

| variant | users | converted | conversion rate |
|---|---|---|---|
| control | 7,136 | 1,414 | 19.815% |
| treatment | 6,864 | 1,814 | 26.428% |

**Naive lift = +6.61 percentage points.** Exactly +6.6127 pp, from 26.4277% minus 19.8150%. In
relative terms that is a 33.4% improvement, with a 95% CI of [+5.22, +8.01] pp, z = 9.29, p < 1e-15.

* n_control = 7,136
* n_treatment = 6,864

I reproduced this first specifically to confirm the claim is arithmetically correct. It is. That
mattered, because it told me the problem was not going to be a bug in someone's query, and I should
be looking at composition instead.

Method: counted rows with `converted == 1` within each variant across the whole file, divided by the
row count for that variant, subtracted.

---

## Q2. Breakdown by segment

| segment | n control | rate control | n treatment | rate treatment | lift (pp) | 95% CI (pp) | p |
|---|---|---|---|---|---|---|---|
| app_store | 925 | 8.76% | 960 | 20.00% | +11.24 | [+8.13, +14.36] | 4.1e-12 |
| influencer | 119 | 23.53% | 131 | 16.79% | -6.74 | [-16.69, +3.22] | 0.184 |
| organic | 1,298 | 35.29% | 2,917 | 35.07% | -0.21 | [-3.34, +2.91] | 0.893 |
| paid_search | 3,353 | 15.18% | 1,459 | 14.39% | -0.79 | [-2.96, +1.39] | 0.482 |
| referral | 1,441 | 23.46% | 1,397 | 26.27% | +2.82 | [-0.37, +5.99] | 0.083 |

This table is where the story falls apart. Four of the five segments show no positive effect, and two
of them are slightly negative. Notice also that no segment actually experienced anything resembling a
+6.6 pp gain. Every segment is either flat, negative, or (in the case of `app_store`) far above it.
When the total points one way and all the parts point another way, the problem is almost always the
mix, which is what sent me to Q5.

### The segment I would not trust: influencer

`influencer` has the second largest swing in the table at -6.74 pp, which is a 28.6% relative move.
If the sign had landed the other way, it would be getting presented as a 6.7 point win for the new
flow. I would not believe it either way:

* Only 250 users total, 119 control and 131 treatment. That is 1.8% of the file and by far the
  smallest segment.
* The 95% CI runs from -16.69 to +3.22 pp. Nearly 20 points wide and it contains zero. p = 0.18.
* The underlying counts are tiny: 28 conversions in control, 22 in treatment. If 9 more treatment
  users had converted, the lift would flip positive. A 9 user swing is well inside ordinary
  week-to-week variation for a segment this size.

`referral` is the other one I would hold loosely. At +2.82 pp with p = 0.083 the direction is
encouraging, but the interval still crosses zero, so the honest description is "worth collecting more
data on", not "a win".

---

## Q3. Mix-adjusted overall lift

For each segment I took its own treatment-minus-control lift and weighted it by that segment's share
of the total 14,000 users, not by how many of that segment landed in treatment.

| segment | segment n | population share | segment lift (pp) | contribution (pp) |
|---|---|---|---|---|
| app_store | 1,885 | 0.1346 | +11.243 | +1.5138 |
| influencer | 250 | 0.0179 | -6.736 | -0.1203 |
| organic | 4,215 | 0.3011 | -0.215 | -0.0647 |
| paid_search | 4,812 | 0.3437 | -0.787 | -0.2705 |
| referral | 2,838 | 0.2027 | +2.815 | +0.5706 |
| **total** | **14,000** | **1.0000** | | **+1.6289** |

**Mix-adjusted lift = +1.63 pp** (+1.6289 pp before rounding).

### Why this differs from Q1

This is Simpson's paradox. The segments convert at very different baseline rates regardless of which
flow they see: `organic` converts at 35.1% overall while `paid_search` converts at 14.9%. The two
variants did not get the same mix of those segments. 69.2% of `organic` users ended up in treatment,
but only 30.3% of `paid_search` users did. So the treatment group is loaded with users who were
always likely to convert and the control group is loaded with users who were not, and roughly 5
points of the topline gap is that difference in composition rather than anything the new flow
accomplished. Weighting each segment's own lift by its share of the total population strips that out
and answers the question we actually care about, which is what the lift would look like if both arms
had seen the same kind of users. The answer is +1.63 pp, about a quarter of the naive figure, and
+1.51 of those +1.63 points come from `app_store` on its own.

---

## Q4. Is there a segment with a real, meaningful positive effect?

Yes. `app_store`.

The evidence that convinced me:

* The effect is large. 8.76% to 20.00% is +11.24 pp in absolute terms and +128% relative. The new
  flow more than doubles conversion for these users.
* It holds up statistically. 95% CI [+8.13, +14.36] pp, z = 6.93, p = 4.1e-12. The whole interval
  sits well above zero, and even the pessimistic end of it (+8.1 pp) would still be the strongest
  result in the experiment.
* The sample is big enough to mean something. 1,885 users split 925 / 960, which is 13.5% of the
  file and more than seven times the size of `influencer`.
* It is not another mix artifact. `app_store` was assigned 50.93% treatment against 49.07% control
  (chi-square = 0.65, p = 0.42), so this particular comparison really is apples to apples. That was
  the specific thing I went and checked before I was willing to believe the number, given what Q5
  turned up.
* It is the only segment that clears the bar. Every other segment has a confidence interval
  containing zero, with p values from 0.08 to 0.89.

One more thing that makes the result coherent rather than surprising: `app_store` control at 8.76%
was the worst performing cell anywhere in the experiment. The old flow was failing app store
installs badly, and the new flow fixes that specific problem. There is no evidence in this data that
it helps anyone else.

What I would recommend: roll out to `app_store`, keep `referral` running to get a cleaner read, and
do not ship to `organic` or `paid_search` on the basis of the topline, since for those two the
measured effect is somewhere between zero and mildly negative.

---

## Q5 (Bonus). Does anything about the assignment look off?

Yes, and this turns out to be the root cause of the misleading topline.

| segment | n control | n treatment | % in treatment | chi-square vs 50/50 | p | segment baseline conv. |
|---|---|---|---|---|---|---|
| app_store | 925 | 960 | 50.93% | 0.65 | 0.42 | 14.48% |
| influencer | 119 | 131 | 52.40% | 0.58 | 0.45 | 20.00% |
| organic | 1,298 | 2,917 | 69.21% | 621.87 | <1e-15 | 35.14% |
| paid_search | 3,353 | 1,459 | 30.32% | 745.48 | <1e-15 | 14.94% |
| referral | 1,441 | 1,397 | 49.22% | 0.68 | 0.41 | 24.84% |
| overall | 7,136 | 6,864 | 49.03% | 5.28 | 0.022 | 23.06% |

Three of the five segments sit close to 50/50, which is what random assignment should produce. The
other two miss badly, and they miss in the worst possible direction:

* `organic`, the highest converting segment in the file at 35.1%, is 69.2% treatment. Landing that
  far from 50/50 by chance is roughly a 1-in-10^137 event.
* `paid_search`, one of the lowest converting segments at 14.9%, is only 30.3% treatment. Same
  story, equally impossible by chance.

The important part is not just that the split is uneven, it is that the unevenness lines up with
baseline conversion quality. Strong traffic went to treatment, weak traffic went to control. That is
exactly the pattern that manufactures a fake win at the topline, and it accounts for the 4.98 point
gap between the naive +6.61 pp and the mix-adjusted +1.63 pp.

Questions I would put to the growth team before trusting any of this:

1. Was bucketing hashed on `user_id`, or did it key off something correlated with acquisition
   channel? A rollout gated on the app install path, or a split done on the marketing side, would
   both produce this.
2. Was treatment ramped up over the course of the month? If treatment ran mostly later and the
   traffic mix shifted toward `organic` during the month, that alone explains the pattern. There is
   no timestamp in the file, so I cannot rule it out from the data I have.
3. Were any users re-bucketed or dropped mid-flight?

Until someone can answer those, there is a caveat on the within-segment numbers too. If assignment
was non-random within a segment on some attribute that is not in this file, then the `organic` and
`paid_search` comparisons are confounded as well, not just the topline. The three cleanly split
segments are not exposed to that concern, and `app_store`, which carries the one finding I am
confident in, is one of them.

---

## How I went about it

* Checked the file for integrity before doing anything else: row count, duplicate `user_id`s, blank
  fields, and the set of values appearing in `converted`, `variant` and `segment`. All clean, so
  nothing was dropped or repaired.
* Reproduced the topline claim so I knew I was looking at the same number leadership was, and
  confirmed it was computed correctly. Once I knew the arithmetic was fine, composition was the
  obvious next place to look.
* Cut the comparison by segment, which broke the story immediately. Four segments flat or negative
  underneath a strongly positive total is the classic shape of Simpson's paradox, so from there I
  went hunting for the confound rather than for a mistake.
* Tested the assignment ratio within each segment against 50/50 with a chi-square test. `organic` at
  69.2% treatment and `paid_search` at 30.3%, both effectively impossible by chance, while the other
  three looked fine. Then I lined the skew up against each segment's baseline conversion rate and
  saw that it runs in the direction that flatters treatment.
* Quantified how much damage that does by computing the population-weighted lift: +1.63 pp against
  +6.61 pp naive, so about three quarters of the headline is composition rather than treatment
  effect.
* Put confidence intervals on every segment rather than stopping at point estimates. That is what
  separates `app_store`, whose interval sits entirely above zero, from `referral` and `influencer`,
  whose intervals do not.
* Stress tested the one positive finding before committing to it. Confirmed `app_store` assignment
  was balanced at 50.93% treatment (p = 0.42), so its lift is not a second mix artifact, and checked
  that 1,885 users is enough to support the size of the claim.

### Dead ends

* I went looking for a data quality explanation first, on the theory that duplicated users inflating
  one arm, malformed `converted` values, or users appearing in both variants would explain the gap.
  Found none of it. The file is clean, which meant the anomaly was structural and real.
* The overall 50.97 / 49.03 split looked like an independent red flag at first (chi-square = 5.28,
  p = 0.022) and I spent time on it before realizing it is just what is left over after the two
  segment level skews partly cancel each other out. It is not a separate problem. Worse, if I had
  stopped at the aggregate test I would have badly understated how broken the randomization actually
  was, since a 1 point overall imbalance looks survivable and a 19 point imbalance inside `organic`
  does not.
* I chased `influencer` for a while as a possible "the new flow hurts creator traffic" finding. The
  -6.74 pp swing and the 28.6% relative move looked like something worth reporting. Then the sample
  size killed it: 250 users, an interval of [-16.69, +3.22], and a 9 user swing flips the sign.
  Dropped it as noise.
* I tried to test whether treatment was ramped over time, which is the most innocent explanation for
  how `organic` ended up at 69% treatment. The file has no timestamp, session or cohort column, so
  there is no way to settle it from this data. It became a question for the growth team instead of
  an answer.
* I considered weighting Q3 by each segment's share of the treatment group rather than its share of
  the total population, and discarded it. Weighting by treatment presence would pull the exact
  imbalance back in that the adjustment exists to remove.
