"""REASON step (modules/reason/research.py) with a fake LLM: no network, deterministic."""
import json

import pytest

from modules.ai import reader
from modules.ai.net import AIError
from modules.reason import research_topic
from modules.reason.research import MIN_SENTENCES, sentence_count, to_text
from modules.video.claims import claims_from_text
from modules.voice_library.language import detect_language

VI = [
    "Nhiều người tin rằng thiên tài luôn khác biệt, nhưng thực ra điều đó không đúng với tất cả mọi người.",
    "Thiên tài thường có trí tò mò rất lớn và luôn đặt câu hỏi về những điều quen thuộc xung quanh.",
    "Họ dành nhiều thời gian luyện tập một lĩnh vực nên nhìn thấy những mối liên hệ mà người khác bỏ qua.",
    "Cách suy nghĩ khác thường giúp họ thử những lời giải mà số đông cho là kỳ lạ hoặc không thể.",
    "Môi trường khuyến khích sáng tạo cũng giúp tài năng phát triển mạnh mẽ hơn theo thời gian.",
    "Sự kiên trì trước thất bại quan trọng không kém trí thông minh bẩm sinh của mỗi người.",
    "Giống như một hạt giống, tài năng cần đất tốt, nước và ánh sáng mới có thể lớn lên.",
    "Một học sinh hay hỏi vì sao bầu trời màu xanh đang rèn luyện chính trí tò mò ấy.",
    "Tóm lại, sự khác biệt của thiên tài đến từ tò mò, luyện tập và môi trường phù hợp.",
    "Ai cũng có thể nuôi dưỡng những thói quen đó để suy nghĩ sáng tạo hơn mỗi ngày.",
]
ROLES = ["hook", "explain", "explain", "explain", "explain", "explain", "example", "example", "summary", "summary"]


class FakeLLM:
    name = "fake"

    def __init__(self, *answers):
        self.answers, self.calls = list(answers), []

    def complete(self, system, user):
        self.calls.append((system, user))
        a = self.answers.pop(0) if len(self.answers) > 1 else self.answers[0]
        if isinstance(a, Exception):
            raise a
        return a


def answer(texts, roles=None, title="Vì sao thiên tài khác biệt"):
    roles = roles or ["explain"] * len(texts)
    return json.dumps({"title": title, "sentences": [{"text": t, "role": r} for t, r in zip(texts, roles)]}, ensure_ascii=False)


@pytest.fixture(autouse=True)
def no_sleep(monkeypatch):
    monkeypatch.setattr(reader, "SLEEP", lambda s: None)


def test_a_vietnamese_question_gives_vietnamese_material_that_becomes_claims():
    llm = FakeLLM(answer(VI, ROLES))
    res = research_topic("Vì sao thiên tài luôn khác biệt?", llm)
    assert res.ok and res.language == "vi" and len(res.sentences) == len(VI)
    assert "Vietnamese" in llm.calls[0][0]
    assert detect_language(res.text) == "vi"
    claims = claims_from_text(res.text)
    assert [c.text for c in claims] == res.sentences            # every sentence survives the existing claim extractor
    assert res.title == "Vì sao thiên tài khác biệt"


def test_paragraphs_follow_the_roles():
    text = to_text([("A b.", "hook"), ("C d.", "explain"), ("E f.", "explain"), ("G h.", "summary")])
    assert text == "A b.\n\nC d. E f.\n\nG h."


def test_bad_sentences_are_dropped_with_a_reason():
    bad = ["Quá ngắn để dùng.",                                                         # too short
           "Năm 2019 có 45 phần trăm người dân tin rằng thiên tài luôn luôn khác biệt hẳn.",  # digits
           "Geniuses are often curious and ask many questions about ordinary everyday things.",  # wrong language
           VI[1]]                                                                          # duplicate
    res = research_topic("Vì sao thiên tài luôn khác biệt?", FakeLLM(answer(VI + bad)))
    assert res.ok and len(res.sentences) == len(VI)
    reasons = " | ".join(res.rejected)
    for why in ("words", "number", "not in Vietnamese", "duplicate"):
        assert why in reasons
    assert not any(ch.isdigit() for ch in res.text)


def test_too_few_sentences_retries_once_then_fails_cleanly():
    few = answer(VI[:3])
    llm = FakeLLM(few, few)
    res = research_topic("Vì sao thiên tài luôn khác biệt?", llm)
    assert not res.ok and len(llm.calls) == 2 and str(MIN_SENTENCES) in res.error and res.text == ""
    llm = FakeLLM(few, answer(VI))
    assert research_topic("Vì sao thiên tài luôn khác biệt?", llm).ok


def test_provider_errors_and_bad_json_never_raise():
    for llm in (FakeLLM(AIError("HTTP 401 from x")), FakeLLM("not json at all"), FakeLLM('{"other": 1}')):
        res = research_topic("Why do prices keep rising?", llm)
        assert not res.ok and res.error and res.provider == "fake"
    assert not research_topic("   ", FakeLLM(answer(VI))).ok
    assert not research_topic("Why?", None).ok


def test_english_question_and_sentence_count_follow_the_duration():
    en = [f"Prices rise when people want to buy more goods than shops can supply in {w} markets." for w in
          ["busy", "quiet", "local", "large", "small", "online", "rural", "city", "weekend", "morning"]]
    llm = FakeLLM(answer(en))
    res = research_topic("Why do prices keep rising?", llm, t_target_s=60)
    assert res.ok and res.language == "en" and "English" in llm.calls[0][0]
    assert sentence_count(60) < sentence_count(90) < sentence_count(120)
    assert f"Give {sentence_count(60)} to" in llm.calls[0][0]


def test_extra_instructions_are_passed_and_missing_end_punctuation_is_fixed():
    texts = [t.rstrip(".") for t in VI]
    llm = FakeLLM(answer(texts))
    res = research_topic("Vì sao thiên tài luôn khác biệt?", llm, instructions="Dành cho học sinh lớp 6")
    assert "Dành cho học sinh lớp 6" in llm.calls[0][1]
    assert all(s.endswith(".") for s in res.sentences)
