"""Hand-written claim fixtures that stand in for the REASON step (not built yet).

ASSUMPTION / SIMULATED: these claims are NOT verified research output. They are generic,
qualitative statements (no statistics) written only so the pipeline demo has input for the
Scene Segmenter. `importance` values are hand-assigned. Replace with real REASON output later.
"""
from __future__ import annotations

from modules.scene_segmenter.segmenter import Claim

_SLEEP = [
    ("science", 0.90, "cause_effect", "Sleep is an active process during which the brain sorts memories and clears waste built up during the day."),
    ("science", 0.70, "step_by_step", "The night is split into repeating cycles of light sleep, deep sleep and dream sleep, each doing different work for the body."),
    ("health", 0.85, "cause_effect", "Going without enough sleep makes it harder to concentrate, remember new facts and react quickly to what happens around you."),
    ("health", 0.75, "cause_effect", "Over months and years, regular short sleep is linked with higher risks of heart problems and weight gain."),
    ("daily_life", 0.80, "step_by_step", "Keeping the same bedtime and wake-up time, even on weekends, helps the body clock settle into a steady rhythm."),
    ("daily_life", 0.65, "cause_effect", "Bright screens late in the evening can delay sleepiness because light tells the brain that it is still daytime."),
    ("daily_life", 0.60, "cause_effect", "A cool, dark and quiet bedroom makes it easier to fall asleep and to stay asleep through the night."),
    ("health", 0.55, "cause_effect", "Caffeine blocks the signals that build up sleep pressure, so a late coffee can keep you awake for hours."),
    ("science", 0.50, "cause_effect", "While you sleep, hormones that support growth and repair are released, which is why rest matters after hard physical effort."),
    ("daily_life", 0.45, "comparison", "Compared with adults, teenagers naturally fall asleep later, which is why early school starts can leave them short of rest."),
    ("daily_life", 0.72, "step_by_step", "To build a better routine, first fix your wake-up time, then dim the lights early, and finally keep screens out of bed."),
    ("risk", 0.68, "cause_effect", "Sleep problems that last for weeks, such as loud snoring with daytime exhaustion, are worth discussing with a doctor."),
    ("health", 0.52, "cause_effect", "Mood is tied to sleep as well, because tired brains react more strongly to stress and recover from it more slowly."),
    ("daily_life", 0.40, "comparison", "A short nap early in the afternoon can refresh you, while a long late nap can make night sleep harder."),
    ("science", 0.58, "analogy", "Think of sleep like charging a phone overnight: skip it and you start the day running on a low battery."),
    ("daily_life", 0.35, "cause_effect", "Heavy meals and alcohol close to bedtime may feel relaxing, but they often break up sleep later in the night."),
]

_INFLATION = [
    ("economics", 0.92, "trend", "Inflation means that prices across the economy rise over time, so each unit of money buys a little less than before."),
    ("economics", 0.70, "step_by_step", "Economists measure it by tracking the cost of a fixed basket of everyday goods and services, called a price index."),
    ("economics", 0.80, "cause_effect", "Demand-pull inflation happens when people want to buy more than the economy can supply, which pushes prices upward."),
    ("economics", 0.75, "cause_effect", "Cost-push inflation appears when producers face higher costs for energy, materials or wages and pass them on to customers."),
    ("policy", 0.60, "cause_effect", "When a central bank creates money much faster than output grows, more money chases the same goods and prices climb."),
    ("policy", 0.85, "cause_effect", "Central banks usually fight inflation by raising interest rates, which makes borrowing more expensive and cools spending."),
    ("household", 0.78, "cause_effect", "Savers lose out when inflation exceeds the interest they earn, because their money loses buying power while it sits in the bank."),
    ("household", 0.55, "cause_effect", "Borrowers with fixed-rate loans can benefit, since they repay with money that is worth less than when they borrowed it."),
    ("risk", 0.72, "cause_effect", "Wages often rise more slowly than prices, so households with fixed incomes feel inflation most strongly."),
    ("risk", 0.66, "comparison", "Mild inflation is generally seen as healthy, whereas very high inflation destroys trust in money and disrupts planning."),
    ("risk", 0.48, "comparison", "Deflation, a fall in the general price level, can also be harmful because people delay purchases and the economy slows."),
    ("household", 0.74, "step_by_step", "To protect your budget, compare prices, review recurring bills, and consider assets that tend to keep pace with rising prices."),
    ("policy", 0.42, "cause_effect", "Governments can also influence prices through taxes, subsidies and limits on how fast certain regulated prices may increase."),
    ("economics", 0.50, "cause_effect", "Because countries trade with each other, a price shock in one place, such as an oil shortage, can spread across borders."),
    ("household", 0.52, "analogy", "Imagine a pizza that stays the same size while the number of dollars used to buy it keeps growing: each slice costs more."),
    ("economics", 0.45, "comparison", "Headline inflation includes food and energy, while core inflation leaves them out because their prices swing sharply from month to month."),
]

_PACKS = {"sleep": _SLEEP, "inflation": _INFLATION}
TOPIC_LABELS = {"sleep": "Why sleep matters", "inflation": "How inflation works"}


def topic_keys() -> list[str]:
    return list(_PACKS)


def get_sample_claims(topic_key: str) -> list[Claim]:
    """Claims of one fixture pack, in source order (`order` = position in the source text)."""
    if topic_key not in _PACKS:
        raise KeyError(f"unknown topic pack {topic_key!r}; choose one of {topic_keys()}")
    prefix = topic_key[:3].upper()
    return [Claim(claim_id=f"{prefix}{i + 1:02d}", text=text, facet=facet, importance=imp,
                  explain_pattern=pattern, has_figure=False, order=i)
            for i, (facet, imp, pattern, text) in enumerate(_PACKS[topic_key])]
