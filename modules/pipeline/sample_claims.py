"""Hand-written claim fixtures that stand in for the REASON step (not built yet).

ASSUMPTION / SIMULATED: these claims are NOT verified research output. They are generic,
qualitative statements (no statistics) written only so the pipeline demo has input for the
Scene Segmenter. `importance` values are hand-assigned. Replace with real REASON output later.

Each pack has a narration language ("en" or "vi"); the Vietnamese packs (`*_vi`) say the same
things as the English ones so a Vietnamese voice has Vietnamese narration to read. For Vietnamese a
"word" is a syllable (whitespace-separated token), as everywhere else in the report.
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

_SLEEP_VI = [
    ("science", 0.90, "cause_effect", "Giấc ngủ là lúc não sắp xếp ký ức và dọn sạch chất thải tích tụ trong ngày."),
    ("science", 0.70, "step_by_step", "Đêm ngủ gồm các chu kỳ lặp lại: ngủ nông, ngủ sâu và ngủ mơ, mỗi giai đoạn làm một việc riêng."),
    ("health", 0.85, "cause_effect", "Thiếu ngủ khiến bạn khó tập trung, khó nhớ điều mới và phản ứng chậm hơn với mọi thứ xung quanh."),
    ("health", 0.75, "cause_effect", "Nhiều năm ngủ ít thường xuyên có liên quan đến nguy cơ tim mạch và tăng cân cao hơn."),
    ("daily_life", 0.80, "step_by_step", "Đi ngủ và thức dậy cùng giờ, kể cả cuối tuần, giúp đồng hồ sinh học chạy ổn định hơn."),
    ("daily_life", 0.65, "cause_effect", "Màn hình sáng buổi tối làm bạn khó buồn ngủ vì ánh sáng báo cho não biết vẫn là ban ngày."),
    ("daily_life", 0.60, "cause_effect", "Phòng ngủ mát, tối và yên tĩnh giúp bạn dễ vào giấc và ngủ liền mạch suốt đêm."),
    ("health", 0.55, "cause_effect", "Caffeine chặn tín hiệu gây buồn ngủ, nên một ly cà phê muộn có thể khiến bạn tỉnh táo nhiều giờ."),
    ("science", 0.50, "cause_effect", "Khi ngủ, cơ thể tiết hormone hỗ trợ tăng trưởng và phục hồi, nên cần nghỉ ngơi sau khi vận động nặng."),
    ("daily_life", 0.45, "comparison", "Thanh thiếu niên tự nhiên buồn ngủ muộn hơn người lớn, nên giờ vào học quá sớm khiến các em thiếu ngủ."),
    ("daily_life", 0.72, "step_by_step", "Để ngủ tốt hơn, hãy cố định giờ thức dậy, rồi giảm đèn sớm và để điện thoại xa giường."),
    ("risk", 0.68, "cause_effect", "Nếu giấc ngủ có vấn đề nhiều tuần, như ngáy to và mệt ban ngày, hãy hỏi bác sĩ."),
    ("health", 0.52, "cause_effect", "Tâm trạng cũng gắn với giấc ngủ: bộ não mệt phản ứng mạnh hơn với căng thẳng và hồi phục chậm hơn."),
    ("daily_life", 0.40, "comparison", "Một giấc ngủ trưa ngắn đầu giờ chiều giúp tỉnh táo, còn ngủ trưa dài và muộn làm đêm khó ngủ hơn."),
    ("science", 0.58, "analogy", "Hãy xem giấc ngủ như sạc điện thoại qua đêm: bỏ qua nó, bạn bắt đầu ngày mới với chiếc pin yếu."),
    ("daily_life", 0.35, "cause_effect", "Bữa ăn nặng và rượu bia sát giờ ngủ có vẻ thư giãn, nhưng thường làm giấc ngủ đứt quãng về sau."),
]

_INFLATION_VI = [
    ("economics", 0.92, "trend", "Lạm phát là khi giá cả tăng dần theo thời gian, nên cùng một đồng tiền mua được ít hàng hơn trước."),
    ("economics", 0.70, "step_by_step", "Nhà kinh tế đo lạm phát bằng giá của một giỏ hàng hóa, dịch vụ cố định, gọi là chỉ số giá."),
    ("economics", 0.80, "cause_effect", "Lạm phát cầu kéo xảy ra khi nhu cầu mua vượt mức nền kinh tế cung ứng được, đẩy giá lên."),
    ("economics", 0.75, "cause_effect", "Lạm phát chi phí đẩy xảy ra khi năng lượng, nguyên liệu hay lương tăng và doanh nghiệp chuyển sang khách hàng."),
    ("policy", 0.60, "cause_effect", "Khi ngân hàng trung ương in tiền nhanh hơn sản lượng tăng, nhiều tiền đuổi theo lượng hàng cũ nên giá tăng."),
    ("policy", 0.85, "cause_effect", "Ngân hàng trung ương thường chống lạm phát bằng cách tăng lãi suất, khiến vay đắt hơn và chi tiêu hạ nhiệt."),
    ("household", 0.78, "cause_effect", "Người gửi tiết kiệm thiệt khi lạm phát cao hơn lãi suất, vì tiền mất dần sức mua ngay trong ngân hàng."),
    ("household", 0.55, "cause_effect", "Người vay lãi suất cố định có thể có lợi vì trả nợ bằng tiền đã mất giá so với lúc vay."),
    ("risk", 0.72, "cause_effect", "Lương thường tăng chậm hơn giá, nên hộ gia đình có thu nhập cố định chịu lạm phát nặng nhất."),
    ("risk", 0.66, "comparison", "Lạm phát nhẹ thường được xem là lành mạnh, còn lạm phát quá cao phá hủy niềm tin và làm rối kế hoạch."),
    ("risk", 0.48, "comparison", "Giảm phát, tức giá chung đi xuống, cũng có hại vì mọi người hoãn mua sắm và nền kinh tế chậm lại."),
    ("household", 0.74, "step_by_step", "Để bảo vệ ngân sách, hãy so sánh giá, rà soát chi định kỳ và cân nhắc tài sản theo kịp giá tăng."),
    ("policy", 0.42, "cause_effect", "Chính phủ cũng tác động đến giá qua thuế, trợ cấp và việc quản lý mức tăng giá một số mặt hàng."),
    ("economics", 0.50, "cause_effect", "Vì các nước giao thương, cú sốc giá ở một nơi, như thiếu dầu, có thể lan sang nhiều nước khác."),
    ("household", 0.52, "analogy", "Hãy hình dung chiếc bánh giữ nguyên cỡ trong khi số tiền mua nó cứ tăng: mỗi miếng sẽ đắt hơn."),
    ("economics", 0.45, "comparison", "Lạm phát chung gồm cả thực phẩm và năng lượng, còn lạm phát lõi loại chúng ra vì giá biến động mạnh."),
]

_PACKS = {"sleep": _SLEEP, "inflation": _INFLATION, "sleep_vi": _SLEEP_VI, "inflation_vi": _INFLATION_VI}
_PACK_LANGUAGE = {"sleep_vi": "vi", "inflation_vi": "vi"}          # every other pack is English
TOPIC_LABELS = {"sleep": "Why sleep matters", "inflation": "How inflation works",
                "sleep_vi": "Giấc ngủ quan trọng thế nào", "inflation_vi": "Lạm phát hoạt động ra sao"}


def pack_language(topic_key: str) -> str:
    if topic_key not in _PACKS:
        raise KeyError(f"unknown topic pack {topic_key!r}; choose one of {topic_keys()}")
    return _PACK_LANGUAGE.get(topic_key, "en")


def topic_keys(language: str | None = None) -> list[str]:
    """Pack keys, optionally only those narrated in `language` ("en" or "vi")."""
    return [k for k in _PACKS if language is None or pack_language(k) == language]


def get_sample_claims(topic_key: str) -> list[Claim]:
    """Claims of one fixture pack, in source order (`order` = position in the source text)."""
    language = pack_language(topic_key)                              # also rejects an unknown key
    prefix = topic_key.split("_")[0][:3].upper() + ("V" if language == "vi" else "")
    return [Claim(claim_id=f"{prefix}{i + 1:02d}", text=text, facet=facet, importance=imp,
                  explain_pattern=pattern, has_figure=False, order=i)
            for i, (facet, imp, pattern, text) in enumerate(_PACKS[topic_key])]
