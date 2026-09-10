"""Тесты глаголов, предложений и справки (pytest).

Запуск: python -m pytest scripts/test_verbs_sentences.py -v
"""
import pytest

from utils import important, sentences, verbs


# ===== Глаголы =====

def test_load_verbs():
    data = verbs.load_verbs()
    assert len(data) == 25
    for v in data:
        assert v["root"] and v["infinitive"] and v["present"]
        assert len(v["present"]) == 4


def test_question_structure():
    q = verbs.build_question()
    assert q["correct"] in q["options"]
    assert len(q["options"]) == 4
    assert len(set(q["options"])) == 4  # без дублей
    assert q["correct_index"] == q["options"].index(q["correct"])


def test_question_uses_only_unambiguous_pronouns():
    # за 100 вопросов не должно выпасть אני/אנחנו
    seen = set()
    for _ in range(100):
        q = verbs.build_question()
        seen.add(q["pronoun_he"])
    assert "אני" not in seen
    assert "אנחנו" not in seen


def test_correct_form_matches_pronoun():
    q = verbs.build_question()
    # правильная форма соответствует местоимению
    pronoun = next(p for p in verbs.PRONOUNS if p["he"] == q["pronoun_he"])
    assert q["correct"] == q["verb"]["present"][pronoun["form"]]


def test_unique_forms_for_identical_genders():
    # у לראות муж./жен. ед. совпадают (רואה) — unique_forms не должен дублировать
    verb = verbs.get_verb_by_root("ר.א.ה")
    uf = verbs.unique_forms(verb)
    assert len(uf) == len(set(uf))


def test_explain_answer():
    q = verbs.build_question()
    text = verbs.explain_answer(q["pronoun_he"], q["correct"])
    assert q["correct"] in text
    assert "род" in text or "местоимение" in text


def test_all_verb_roots_in_roots_json():
    from utils.roots import load_roots

    root_keys = {r["root"] for r in load_roots()}
    for v in verbs.load_verbs():
        assert v["root"] in root_keys, f"корень {v['root']} отсутствует в roots.json"


def test_all_words_includes_infinitives():
    from utils.logic import get_all_words

    words = get_all_words()
    verb_words = [w for w in words if w.get("pos") == "verb"]
    assert len(verb_words) == 25
    assert all(w.get("root") for w in verb_words)


# ===== Предложения =====

def test_load_exercises():
    data = sentences.load_exercises()
    assert len(data) == 22


def test_correct_sentence():
    ex = next(e for e in sentences.load_exercises() if e["id"] == "ex_001")
    res = sentences.check_sentence(ex, ["דויד", "גר", "במוסקבה"])
    assert res["ok"] is True


def test_any_pattern_is_accepted():
    ex = next(e for e in sentences.load_exercises() if e["id"] == "ex_001")
    for pattern in ex["correct_patterns"]:
        assert sentences.check_sentence(ex, pattern)["ok"] is True


def test_extra_word_feedback():
    ex = next(e for e in sentences.load_exercises() if e["id"] == "ex_001")
    res = sentences.check_sentence(ex, ["דויד", "גר", "במוסקבה", "דינה"])
    assert res["ok"] is False
    assert res["feedback_type"] == "extra_word"


def test_missing_word_feedback():
    ex = next(e for e in sentences.load_exercises() if e["id"] == "ex_001")
    res = sentences.check_sentence(ex, ["דויד", "גר"])
    assert res["ok"] is False
    assert res["feedback_type"] == "missing_word"


def test_wrong_order_feedback():
    ex = next(e for e in sentences.load_exercises() if e["id"] == "ex_001")
    res = sentences.check_sentence(ex, ["גר", "דויד", "במוסקבה"])
    assert res["ok"] is False
    assert res["feedback_type"] == "wrong_order"


# ===== Важно =====

def test_important_sections():
    sections = important.load_sections()
    assert len(sections) == 4
    ids = {s["id"] for s in sections}
    assert {"reading", "word_formation", "verbs", "sentences"} <= ids


def test_render_section():
    section = important.get_section("verbs")
    text = important.render_section(section)
    assert "пааль" in text.lower()
    assert "котэв" in text
