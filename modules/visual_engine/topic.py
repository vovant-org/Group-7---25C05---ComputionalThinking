"""Step 1 - topic analysis: domain, audience, concepts and the relations between them.

Deterministic lexicon (English + Vietnamese), no model. `CONCEPTS` maps a visual concept (an object the engine
can draw) to the domains it belongs to and the words that mention it. A domain is chosen by weighted counting
(topic words count 3x, claim words 1x), so "Why does Ho Chi Minh City flood?" -> weather, "Why do prices rise?"
-> economy. Relations ("A causes B", "A orbits B", money "flows") and the trend direction (rise / fall) pick
between alternative motions later.

ASSUMPTION (not measured on real data): the word lists are our own. They are small on purpose; a topic whose
words are not listed falls back to the generic kit instead of guessing.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from modules.visual_engine import textmatch as T

DOMAINS = ("sleep", "economy", "nature", "space", "weather", "tech", "generic")

# concept -> (domains, keywords).  Order inside a domain is the order of the default pool in kits.py.
CONCEPTS: dict[str, tuple[tuple[str, ...], list[str]]] = {
    "moon": (("space", "sleep"), ["moon", "night", "bedtime", "trăng", "mặt trăng", "đêm", "ban đêm"]),
    "star": (("space", "sleep"), ["star", "stars", "galaxy", "ngôi sao", "thiên hà"]),
    "bed": (("sleep",), ["sleep", "asleep", "bed", "nap", "dream", "giấc ngủ", "ngủ", "giường", "giấc mơ"]),
    "brain": (("sleep",), ["brain", "memory", "memories", "neuron", "não", "trí nhớ", "ký ức"]),
    "clock": (("sleep", "generic"), ["clock", "schedule", "routine", "rhythm", "hour", "đồng hồ", "lịch trình",
                                     "nhịp", "giờ", "thói quen"]),
    "heart": (("sleep",), ["heart", "blood", "health", "tim", "tim mạch", "sức khỏe", "huyết áp"]),
    "coin": (("economy",), ["money", "coin", "cash", "income", "wage", "salary", "saving", "tiền", "đồng tiền",
                            "thu nhập", "lương", "tiết kiệm"]),
    "bank": (("economy",), ["bank", "interest", "loan", "credit", "ngân hàng", "lãi suất", "vay", "tín dụng"]),
    "basket": (("economy",), ["basket", "goods", "shopping", "grocery", "market", "hàng hóa", "giỏ hàng", "chợ",
                              "mua sắm", "siêu thị"]),
    "tag": (("economy",), ["price", "cost", "expensive", "giá", "giá cả", "chi phí", "đắt"]),
    "bars_up": (("economy", "tech"), ["inflation", "growth", "increase", "rise", "rising", "decrease", "decline",
                                      "fall", "trend", "gdp", "lạm phát", "tăng", "giảm", "tăng trưởng", "xu hướng"]),
    "animal": (("nature",), ["animal", "deer", "elephant", "wildlife", "mammal", "herd", "migration", "động vật",
                             "thú", "voi", "hươu", "di cư"]),
    "bird": (("nature",), ["bird", "fly", "flight", "wing", "chim", "bay", "cánh"]),
    "fish": (("nature",), ["fish", "ocean", "sea", "river", "aquatic", "cá", "biển", "sông", "đại dương"]),
    "tree": (("nature",), ["tree", "forest", "wood", "cây", "rừng", "cây cối"]),
    "sprout": (("nature",), ["plant", "seed", "sprout", "germinat", "photosynthesis", "crop", "harvest", "hạt",
                             "mầm", "nảy mầm", "quang hợp", "trồng trọt", "nông nghiệp"]),
    "sun": (("nature", "space"), ["sun", "sunlight", "solar", "daylight", "mặt trời", "ánh nắng"]),
    "drop": (("nature", "weather"), ["water", "rain", "rainfall", "droplet", "nước", "mưa", "giọt"]),
    "cloud": (("weather",), ["cloud", "storm", "weather", "monsoon", "mây", "bão", "thời tiết", "gió mùa"]),
    "planet": (("space",), ["planet", "orbit", "solar system", "mars", "jupiter", "venus", "saturn", "hành tinh",
                            "quỹ đạo", "hệ mặt trời", "sao hỏa", "sao mộc"]),
    "earth": (("space", "weather"), ["earth", "globe", "climate", "global warming", "trái đất", "khí hậu",
                                     "nóng lên toàn cầu"]),
    "rocket": (("space", "tech"), ["rocket", "spacecraft", "launch", "satellite", "astronaut", "tên lửa", "vệ tinh",
                                   "phi hành gia"]),
    "building": (("weather", "economy"), ["city", "urban", "building", "street", "thành phố", "đô thị", "tòa nhà",
                                          "đường phố", "sài gòn", "hcm"]),
    "flood": (("weather",), ["flood", "tide", "sea level", "drainage", "drain", "ngập", "ngập lụt", "triều cường",
                             "thoát nước", "nước dâng", "mực nước"]),
    "chip": (("tech",), ["computer", "chip", "processor", "cpu", "software", "code", "algorithm",
                         "artificial intelligence", "máy tính", "vi xử lý", "phần mềm", "thuật toán", "lập trình",
                         "trí tuệ nhân tạo"]),
    "signal": (("tech",), ["internet", "network", "wifi", "online", "signal", "data", "packet", "router", "server", "website", "mạng",
                           "dữ liệu", "kết nối", "gói tin", "máy chủ", "trang web"]),
    "book": (("generic",), ["book", "read", "study", "learn", "school", "student", "history", "sách", "đọc",
                            "học sinh", "học tập", "trường học", "kiến thức"]),
    "bulb": (("generic",), ["idea", "imagine", "think", "creative", "innovation", "ý tưởng", "sáng tạo",
                            "tưởng tượng", "nghĩ"]),
}
CONCEPT_DOMAINS = {k: v[0] for k, v in CONCEPTS.items()}

_RISE = ["rise", "rising", "increase", "grow", "climb", "higher", "tăng", "dâng", "cao hơn"]
_FALL = ["fall", "decline", "decrease", "drop", "lower", "giảm", "hạ", "thấp hơn", "mất giá"]
_RELATIONS = {                      # relation -> cue words
    "orbits": ["orbit", "revolve", "quay quanh", "quỹ đạo"],
    "flows": ["flow", "circulat", "spend", "pay", "luân chuyển", "chảy", "chi tiêu", "trả"],
    "grows": ["grow", "sprout", "germinat", "phát triển", "lớn lên", "nảy mầm", "mọc"],
    "causes": ["cause", "lead to", "result in", "because", "so ", "gây", "dẫn đến", "khiến", "vì", "nên"],
}
_AUDIENCE = {"kids": ["kid", "child", "children", "trẻ em", "bé"],
             "students": ["student", "school", "class", "học sinh", "sinh viên", "lớp"]}
ACTOR_DOMAINS = frozenset({"sleep", "economy", "weather", "generic"})      # a stick figure explains these


@dataclass(frozen=True)
class Relation:
    a: str
    verb: str
    b: str | None = None
    scene_text: str = ""


@dataclass(frozen=True)
class TopicProfile:
    domain: str
    scores: dict
    audience: str
    concepts: tuple                       # concept keys of the whole video, strongest first
    relations: tuple = ()
    trend: int = 0                        # +1 rising words dominate, -1 falling, 0 none/mixed
    vietnamese: bool = False

    @property
    def actor(self) -> bool:
        return self.domain in ACTOR_DOMAINS


def find_concepts(text: str, vietnamese: bool | None = None) -> list[tuple[str, int]]:
    """[(concept, first word index)] in order of first mention."""
    words = T.tokens(text)
    vn = T.has_vietnamese_marks(text) if vietnamese is None else vietnamese
    hits = []
    for key, (_, kws) in CONCEPTS.items():
        idx = T.find_keywords(words, kws, vn)
        if idx is not None:
            hits.append((key, idx))
    return sorted(hits, key=lambda h: (h[1], h[0]))


def trend_of(text: str) -> int:
    words, vn = T.tokens(text), T.has_vietnamese_marks(text)
    up = T.find_keywords(words, _RISE, vn)
    down = T.find_keywords(words, _FALL, vn)
    if up is None and down is None:
        return 0
    if down is None:
        return 1
    if up is None:
        return -1
    return 1 if up < down else -1                      # the first trend word wins ("prices rise, then fall" = rise)


def relations_in(text: str) -> list[Relation]:
    words, vn = T.tokens(text), T.has_vietnamese_marks(text)
    found = find_concepts(text, vn)
    out = []
    for verb, cues in _RELATIONS.items():
        if T.find_keywords(words, cues, vn) is None:
            continue
        if verb == "causes" and len(found) < 2:
            continue
        a = found[0][0] if found else ""
        b = found[1][0] if len(found) > 1 else None
        out.append(Relation(a, verb, b, text[:60]))
    return out


def analyse_topic(topic: str, claim_texts: list[str]) -> TopicProfile:
    """Domain, audience, concepts and relations of the whole video (computed once)."""
    all_text = " ".join([topic] + list(claim_texts))
    vn = T.has_vietnamese_marks(all_text)
    scores = {d: 0.0 for d in DOMAINS}
    counts: dict[str, float] = {}
    for weight, text in [(3.0, topic)] + [(1.0, c) for c in claim_texts]:
        for key, _ in find_concepts(text, vn):
            counts[key] = counts.get(key, 0.0) + weight
            doms = CONCEPT_DOMAINS[key]
            for d in doms:
                scores[d] += weight / len(doms)
    best = max((d for d in DOMAINS if d != "generic"), key=lambda d: (scores[d], -DOMAINS.index(d)))
    domain = best if scores[best] >= 2.0 else "generic"
    scores["generic"] = max(scores["generic"], 0.0)
    words = T.tokens(all_text)
    audience = next((a for a, cues in _AUDIENCE.items() if T.find_keywords(words, cues, vn) is not None), "general")
    concepts = tuple(sorted(counts, key=lambda k: (-counts[k], k)))
    rels = tuple(r for text in [topic] + list(claim_texts) for r in relations_in(text))
    return TopicProfile(domain=domain, scores={k: round(v, 2) for k, v in scores.items()}, audience=audience,
                        concepts=concepts, relations=rels, trend=trend_of(all_text), vietnamese=vn)
