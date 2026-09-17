"""
Onboarding Experiment Investigation
-----------------------------------
Analysis of experiment_results.csv (A/B test of a new onboarding flow).

Standard library only (csv, math, statistics).

Usage:
    python3 analyze.py [path/to/experiment_results.csv]

Prints every number quoted in ANSWERS.md and writes answers.json.
"""

import csv
import json
import math
import sys
from collections import defaultdict
from statistics import NormalDist

CSV_PATH = sys.argv[1] if len(sys.argv) > 1 else "experiment_results.csv"
JSON_OUT = "answers.json"

NORM = NormalDist()


# ---------------------------------------------------------------- load / checks

def load(path):
    with open(path, newline="") as fh:
        rows = list(csv.DictReader(fh))
    for r in rows:
        r["converted"] = int(r["converted"])
    return rows


def data_quality(rows):
    """Integrity checks run before any analysis (all passed on the given file)."""
    ids = [r["user_id"] for r in rows]
    return {
        "n_rows": len(rows),
        "duplicate_user_ids": len(ids) - len(set(ids)),
        "rows_with_blank_fields": sum(
            1 for r in rows if any(v is None or v == "" for v in r.values())
        ),
        "converted_values": sorted({r["converted"] for r in rows}),
        "variant_values": sorted({r["variant"] for r in rows}),
        "segment_values": sorted({r["segment"] for r in rows}),
    }


# ---------------------------------------------------------------- stats helpers

def rate(rows):
    return sum(r["converted"] for r in rows) / len(rows) if rows else float("nan")


def split(rows):
    control = [r for r in rows if r["variant"] == "control"]
    treatment = [r for r in rows if r["variant"] == "treatment"]
    return control, treatment


def compare(rows):
    """Treatment-minus-control lift in percentage points, with CI and two-proportion z-test."""
    control, treatment = split(rows)
    p_c, p_t = rate(control), rate(treatment)
    n_c, n_t = len(control), len(treatment)
    diff = p_t - p_c

    # unpooled SE for the confidence interval
    se = math.sqrt(p_c * (1 - p_c) / n_c + p_t * (1 - p_t) / n_t)
    # pooled SE for the null-hypothesis test
    p_pool = (sum(r["converted"] for r in rows)) / (n_c + n_t)
    se_pool = math.sqrt(p_pool * (1 - p_pool) * (1 / n_c + 1 / n_t))

    z = diff / se_pool if se_pool else float("nan")
    p_value = 2 * (1 - NORM.cdf(abs(z)))

    return {
        "n_control": n_c,
        "n_treatment": n_t,
        "n_total": n_c + n_t,
        "rate_control": p_c,
        "rate_treatment": p_t,
        "lift_pp": diff * 100,
        "relative_lift_pct": (diff / p_c * 100) if p_c else float("nan"),
        "ci95_low_pp": (diff - 1.96 * se) * 100,
        "ci95_high_pp": (diff + 1.96 * se) * 100,
        "z": z,
        "p_value": p_value,
        "share_treatment_pct": n_t / (n_c + n_t) * 100,
    }


def srm_chi2(n_control, n_treatment):
    """Sample-ratio-mismatch test against an expected 50/50 split (1 dof)."""
    total = n_control + n_treatment
    expected = total / 2
    chi2 = (n_control - expected) ** 2 / expected + (n_treatment - expected) ** 2 / expected
    p_value = 2 * (1 - NORM.cdf(math.sqrt(chi2)))
    return chi2, p_value


# ---------------------------------------------------------------- the questions

def main():
    rows = load(CSV_PATH)
    checks = data_quality(rows)

    by_segment = defaultdict(list)
    for r in rows:
        by_segment[r["segment"]].append(r)
    segments = sorted(by_segment)
    total_users = len(rows)

    print("=" * 78)
    print("DATA QUALITY CHECKS")
    print("=" * 78)
    for k, v in checks.items():
        print(f"  {k:26} {v}")

    # ---- Q1: naive overall lift -------------------------------------------
    overall = compare(rows)
    print()
    print("=" * 78)
    print("Q1  NAIVE OVERALL COMPARISON")
    print("=" * 78)
    print(f"  control    n = {overall['n_control']:>5}   conversion = {overall['rate_control']*100:6.3f}%")
    print(f"  treatment  n = {overall['n_treatment']:>5}   conversion = {overall['rate_treatment']*100:6.3f}%")
    print(f"  naive lift = {overall['lift_pp']:+.4f} pp  "
          f"(95% CI [{overall['ci95_low_pp']:+.2f}, {overall['ci95_high_pp']:+.2f}] pp, "
          f"z = {overall['z']:.2f}, p = {overall['p_value']:.2e})")

    # ---- Q2: per-segment breakdown ----------------------------------------
    print()
    print("=" * 78)
    print("Q2  BREAKDOWN BY SEGMENT")
    print("=" * 78)
    header = (f"  {'segment':<12}{'n_ctrl':>7}{'rate_c':>9}{'n_trt':>7}{'rate_t':>9}"
              f"{'lift_pp':>10}{'95% CI (pp)':>20}{'p':>10}")
    print(header)
    print("  " + "-" * (len(header) - 2))
    per_segment = {}
    for s in segments:
        st = compare(by_segment[s])
        per_segment[s] = st
        ci = f"[{st['ci95_low_pp']:+6.2f},{st['ci95_high_pp']:+6.2f}]"
        print(f"  {s:<12}{st['n_control']:>7}{st['rate_control']*100:>8.2f}%"
              f"{st['n_treatment']:>7}{st['rate_treatment']*100:>8.2f}%"
              f"{st['lift_pp']:>+10.3f}{ci:>20}{st['p_value']:>10.2e}")

    smallest = min(segments, key=lambda s: per_segment[s]["n_total"])
    widest = max(segments, key=lambda s: per_segment[s]["ci95_high_pp"] - per_segment[s]["ci95_low_pp"])
    print(f"\n  smallest segment: {smallest} (n = {per_segment[smallest]['n_total']})")
    print(f"  widest CI:        {widest} "
          f"({per_segment[widest]['ci95_high_pp'] - per_segment[widest]['ci95_low_pp']:.1f} pp wide)")

    # ---- Q3: mix-adjusted lift --------------------------------------------
    print()
    print("=" * 78)
    print("Q3  MIX-ADJUSTED OVERALL LIFT")
    print("=" * 78)
    print(f"  {'segment':<12}{'seg_n':>8}{'pop_share':>12}{'lift_pp':>11}{'contribution':>15}")
    print("  " + "-" * 56)
    mix_adjusted = 0.0
    for s in segments:
        st = per_segment[s]
        share = st["n_total"] / total_users
        contribution = share * st["lift_pp"]
        mix_adjusted += contribution
        print(f"  {s:<12}{st['n_total']:>8}{share:>12.4f}{st['lift_pp']:>+11.3f}{contribution:>+15.4f}")
    print("  " + "-" * 56)
    print(f"  {'TOTAL':<12}{total_users:>8}{1.0:>12.4f}{'':>11}{mix_adjusted:>+15.4f}")
    print(f"\n  mix-adjusted lift = {mix_adjusted:+.2f} pp   "
          f"(naive = {overall['lift_pp']:+.2f} pp, gap = {overall['lift_pp'] - mix_adjusted:.2f} pp)")

    # ---- Q4: where the effect is real -------------------------------------
    print()
    print("=" * 78)
    print("Q4  SEGMENTS WITH A DEFENSIBLE POSITIVE EFFECT")
    print("=" * 78)
    real = [s for s in segments
            if per_segment[s]["ci95_low_pp"] > 0 and per_segment[s]["p_value"] < 0.05]
    for s in segments:
        st = per_segment[s]
        verdict = "REAL" if s in real else "not distinguishable from zero"
        print(f"  {s:<12} lift {st['lift_pp']:+7.3f} pp  "
              f"(relative {st['relative_lift_pct']:+6.1f}%)  p = {st['p_value']:.2e}  -> {verdict}")
    best = max(real, key=lambda s: per_segment[s]["lift_pp"]) if real else ""
    print(f"\n  conclusion: {best or 'none'}")

    # ---- Q5: assignment audit ---------------------------------------------
    print()
    print("=" * 78)
    print("Q5  ASSIGNMENT AUDIT (sample ratio mismatch vs expected 50/50)")
    print("=" * 78)
    print(f"  {'segment':<12}{'n_ctrl':>8}{'n_trt':>8}{'%treatment':>13}{'chi2':>12}{'p':>12}"
          f"{'baseline':>11}")
    print("  " + "-" * 74)
    for s in segments:
        st = per_segment[s]
        chi2, p_value = srm_chi2(st["n_control"], st["n_treatment"])
        baseline = rate(by_segment[s]) * 100
        print(f"  {s:<12}{st['n_control']:>8}{st['n_treatment']:>8}"
              f"{st['share_treatment_pct']:>12.2f}%{chi2:>12.2f}{p_value:>12.2e}{baseline:>10.2f}%")
    chi2_all, p_all = srm_chi2(overall["n_control"], overall["n_treatment"])
    print(f"  {'OVERALL':<12}{overall['n_control']:>8}{overall['n_treatment']:>8}"
          f"{overall['share_treatment_pct']:>12.2f}%{chi2_all:>12.2f}{p_all:>12.2e}"
          f"{rate(rows)*100:>10.2f}%")

    # ---- answers.json ------------------------------------------------------
    answers = {
        "q1_naive_lift_pp": round(overall["lift_pp"], 2),
        "q1_n_control": overall["n_control"],
        "q1_n_treatment": overall["n_treatment"],
        "q2_untrustworthy_segment": smallest,
        "q3_mix_adjusted_lift_pp": round(mix_adjusted, 2),
        "q4_real_effect_segment": best or "none",
    }
    with open(JSON_OUT, "w") as fh:
        json.dump(answers, fh, indent=2)
        fh.write("\n")
    print()
    print("=" * 78)
    print(f"WROTE {JSON_OUT}")
    print("=" * 78)
    print(json.dumps(answers, indent=2))


if __name__ == "__main__":
    main()
