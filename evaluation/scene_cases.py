"""Hand-written Scene Segmenter cases built from the two worked examples of report 5.8.

Each case = verified claims (what REASON would output) + which claims paraphrase the same
IDEA + which ideas are GOLD (must appear in the video). The algorithms never see idea ids.
All importance scores, paraphrases, distractors and gold flags were written by the AI assistant
from the report's text: TEAM MUST REVIEW AND CORRECT THEM (and add the 3 hard cases each
member prepares). Importance of anecdotes/distractors is deliberately high-ish: LLM scorers
often rate vivid but secondary facts highly.
"""
from __future__ import annotations

from dataclasses import dataclass

from modules.scene_segmenter.segmenter import Claim


@dataclass
class SceneCase:
    id: str
    t_target: int
    claims: list[Claim]
    idea_of: dict[str, str]          # claim_id -> idea id
    gold: set[str]                   # idea ids that must be covered


def _build(case_id, t, rows):
    claims, idea_of, gold = [], {}, set()
    for k, (idea, is_gold, facet, imp, pattern, fig, text) in enumerate(rows):
        cid = f"{case_id}{k + 1:02d}"
        claims.append(Claim(cid, text, facet, imp, pattern, fig, order=k))
        idea_of[cid] = idea
        if is_gold:
            gold.add(idea)
    return SceneCase(case_id, t, claims, idea_of, gold)


# (idea, gold?, facet, importance, explain_pattern, has_figure, text)
SLEEP = _build("sleep", 60, [
    ("hours", True, "science", 0.90, "step_by_step", True, "Most adults need about 7 to 9 hours of sleep per night."),
    ("hours", True, "science", 0.88, "step_by_step", True, "Adults generally require seven to nine hours of sleep every night."),
    ("cycles", True, "science", 0.84, "cause_effect", True, "Sleep runs in cycles of light, deep and dream sleep that last roughly 90 minutes."),
    ("deep", True, "science", 0.86, "cause_effect", False, "In deep sleep the body repairs tissue and the brain appears to clear waste built up during the day."),
    ("deep", True, "science", 0.83, "cause_effect", False, "During deep sleep, tissues are repaired and the brain flushes out the day's waste products."),
    ("rem", True, "science", 0.82, "cause_effect", False, "Dream sleep helps the brain sort experiences and consolidate memory."),
    ("rem", True, "science", 0.80, "cause_effect", False, "REM sleep supports memory by sorting through the day's experiences."),
    ("short", True, "health", 0.78, "cause_effect", False, "Short sleep reduces attention and reaction time and worsens mood."),
    ("chronic", True, "health", 0.76, "cause_effect", False, "Chronic sleep loss is linked to higher health risks."),
    ("chronic", True, "health", 0.74, "cause_effect", False, "Long-term lack of sleep is associated with weaker immunity and heart disease."),
    ("habits", True, "practical", 0.70, "step_by_step", False, "A regular schedule, dim light before bed and no screens help sleep."),
    ("habits", True, "practical", 0.68, "step_by_step", False, "Going to bed at the same time, dimming the lights and avoiding screens improves sleep."),
    ("dolphin", False, "science", 0.75, "analogy", False, "Some animals, such as dolphins, sleep with only half of the brain at a time."),
    ("third", False, "science", 0.72, "analogy", True, "The average person spends about a third of their life asleep."),
    ("caffeine", False, "practical", 0.66, "cause_effect", True, "Caffeine takes about five hours to lose half of its effect in the body."),
    ("record", False, "society", 0.79, "analogy", True, "In 1964 a high school student stayed awake for 11 days as a science project."),
    ("apps", False, "society", 0.55, "trend", False, "Sleep tracking apps have become popular among young adults."),
    ("nap", False, "practical", 0.50, "step_by_step", False, "A short nap in the early afternoon can restore alertness for a few hours."),
    ("teen", False, "science", 0.62, "comparison", False, "Teenagers tend to fall asleep later than children and adults because their body clock shifts during puberty."),
    ("light", False, "science", 0.60, "cause_effect", False, "Bright light in the evening delays the release of melatonin, the hormone that signals the body it is time to sleep."),
    ("snore", False, "health", 0.58, "cause_effect", False, "Loud snoring with pauses in breathing can be a sign of sleep apnea and should be checked by a doctor."),
    ("shift", False, "society", 0.64, "cause_effect", False, "Night shift workers often struggle with sleep because their schedule conflicts with the natural day and night rhythm."),
    ("jetlag", False, "science", 0.57, "cause_effect", False, "Jet lag appears when travel across time zones leaves the body clock out of step with local time."),
    ("room", False, "practical", 0.61, "step_by_step", False, "A cool, dark and quiet bedroom makes it easier to fall asleep and stay asleep through the night."),
    ("school", False, "society", 0.63, "comparison", False, "Some schools have moved their start time later to give teenagers more sleep and better attention in class."),
    ("alcohol", False, "health", 0.56, "cause_effect", False, "Alcohol may help people fall asleep faster but it usually makes sleep lighter and more broken later in the night."),
    ("babies", False, "science", 0.52, "comparison", True, "Newborn babies sleep around 14 to 17 hours a day, much more than adults."),
    ("cat", False, "society", 0.48, "analogy", False, "Cats are famous for sleeping most of the day, which is why people say they are the champions of napping."),
])

INFLATION = _build("infl", 60, [
    ("def", True, "economics", 0.92, "cause_effect", False, "Inflation is a general rise in prices, so each unit of money buys less."),
    ("def", True, "economics", 0.90, "cause_effect", False, "Inflation means prices rise across the economy and money loses buying power."),
    ("cpi", True, "economics", 0.86, "step_by_step", False, "Inflation is measured by the CPI, the price of a fixed basket of everyday goods."),
    ("example", True, "economics", 0.84, "trend", True, "If the basket rises from 100 to 103.5, inflation is 3.5 percent."),
    ("demand", True, "economics", 0.88, "cause_effect", False, "Demand-pull inflation happens when demand is greater than supply."),
    ("demand", True, "economics", 0.85, "cause_effect", False, "When buyers want more than the economy can supply, sellers raise prices."),
    ("cost", True, "economics", 0.87, "cause_effect", False, "Cost-push inflation happens when fuel, wages or materials become more expensive."),
    ("money", True, "economics", 0.80, "cause_effect", False, "Prices rise when the money supply grows faster than output."),
    ("savers", True, "society", 0.78, "comparison", True, "Savings paying 2 percent while inflation is 3.5 percent lose 1.5 percent in real value."),
    ("rates", True, "policy", 0.82, "cause_effect", False, "Central banks raise interest rates to slow spending and cool prices."),
    ("rates", True, "policy", 0.79, "cause_effect", False, "To cool inflation, central banks make borrowing more expensive by raising rates."),
    ("history", False, "society", 0.74, "trend", False, "Some countries have lived through periods of extremely high inflation."),
    ("target", False, "policy", 0.70, "comparison", True, "Many central banks aim for an inflation rate of about 2 percent."),
    ("gold", False, "economics", 0.62, "analogy", False, "Gold is often described as a hedge against rising prices."),
    ("indexes", False, "economics", 0.58, "comparison", False, "Different countries measure inflation with different price indexes."),
    ("wages", False, "society", 0.66, "cause_effect", False, "Wages sometimes rise after prices, so workers feel the squeeze first."),
    ("housing", False, "economics", 0.64, "cause_effect", False, "Rising rents and house prices often make up a large part of the increase in the price index."),
    ("expect", False, "economics", 0.68, "cause_effect", False, "When people expect prices to keep rising, they ask for higher wages and firms raise prices earlier, which can keep inflation going."),
    ("deflation", False, "economics", 0.60, "comparison", False, "The opposite of inflation is deflation, when prices fall over time and people may delay buying things."),
    ("food", False, "society", 0.63, "cause_effect", False, "Food and fuel prices are often the first that households notice because they buy them every week."),
    ("pension", False, "society", 0.57, "cause_effect", False, "People living on fixed pensions are hit hard by inflation because their income does not rise with prices."),
    ("debt", False, "economics", 0.55, "comparison", False, "Inflation can make old debts easier to repay in real terms because the money borrowed is worth less later."),
    ("tax", False, "policy", 0.59, "cause_effect", False, "Governments may cut taxes or give subsidies to ease the burden of rising prices on families."),
    ("import", False, "economics", 0.61, "cause_effect", False, "A weaker currency makes imported goods more expensive, which can push up prices in shops."),
    ("supply", False, "economics", 0.66, "cause_effect", False, "Supply chain disruptions, such as port delays, can create shortages that push prices higher for a while."),
    ("hyper", False, "society", 0.52, "trend", True, "In extreme cases prices can double within a month, and people rush to spend money before it loses value."),
])

CASES = [SLEEP, INFLATION]
