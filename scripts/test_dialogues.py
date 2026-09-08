"""Тесты модели диалогов и недельного цикла (pytest).

Запуск из корня проекта:
    python -m pytest scripts/test_dialogues.py -v
"""
from datetime import date, timedelta

import pytest

import utils.database as db
from utils import dialogues


@pytest.fixture
def clean_db(tmp_path, monkeypatch):
    """Временная БД на каждый тест."""
    db_path = tmp_path / "test.db"
    monkeypatch.setattr(db, "DB_PATH", db_path)
    db.init_db()
    yield


# ===== Таблицы =====

def test_init_db_creates_dialogue_tables(tmp_path, monkeypatch):
    db_path = tmp_path / "new.db"
    monkeypatch.setattr(db, "DB_PATH", db_path)
    db.init_db()
    conn = db.get_connection()
    tables = {r["name"] for r in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table'"
    )}
    conn.close()
    assert "user_dialogues" in tables
    assert "user_settings" in tables


# ===== Сбор диалога =====

def test_collect_dialogue_full(clean_db):
    res = db.collect_dialogue(1, "d01", "full")
    assert res == "full"
    assert db.get_dialogue_status(1, "d01") == "full"


def test_collect_partial_then_full_upgrades(clean_db):
    db.collect_dialogue(1, "d01", "partial")
    res = db.collect_dialogue(1, "d01", "full")
    assert res == "full"
    assert db.get_dialogue_status(1, "d01") == "full"


def test_full_not_downgraded_by_partial(clean_db):
    db.collect_dialogue(1, "d01", "full")
    res = db.collect_dialogue(1, "d01", "partial")
    assert res is None  # повторный partial не перезаписывает full
    assert db.get_dialogue_status(1, "d01") == "full"


def test_collect_same_dialogue_no_duplicates(clean_db):
    db.collect_dialogue(1, "d01", "full")
    db.collect_dialogue(1, "d01", "full")
    rows = db.get_collected_dialogues(1)
    assert len(rows) == 1


def test_status_none_for_unsaved(clean_db):
    assert db.get_dialogue_status(1, "d99") is None


def test_mark_played_increments(clean_db):
    db.mark_dialogue_played(1, "d01")
    db.mark_dialogue_played(1, "d01")
    rows = db.get_collected_dialogues(1)
    assert len(rows) == 1
    assert rows[0]["plays"] == 2
    assert rows[0]["status"] == "partial"


def test_collected_list(clean_db):
    db.collect_dialogue(1, "d01", "full")
    db.collect_dialogue(1, "d02", "partial")
    rows = db.get_collected_dialogues(1)
    ids = [r["dialogue_id"] for r in rows]
    assert ids == ["d01", "d02"]


def test_users_isolated(clean_db):
    db.collect_dialogue(1, "d01", "full")
    assert db.get_dialogue_status(2, "d01") is None


# ===== Настройки рассылки (отписка) =====

def test_daily_default_enabled(clean_db):
    assert db.get_dialogue_daily_enabled(1) == 1


def test_unsubscribe_and_resubscribe(clean_db):
    db.set_dialogue_daily(1, False)
    assert db.get_dialogue_daily_enabled(1) == 0
    db.set_dialogue_daily(1, True)
    assert db.get_dialogue_daily_enabled(1) == 1


def test_settings_isolated(clean_db):
    db.set_dialogue_daily(1, False)
    assert db.get_dialogue_daily_enabled(2) == 1


# ===== Каталог диалогов =====

def test_load_dialogues_correct():
    dlg_list = dialogues.load_dialogues()
    assert len(dlg_list) == 6
    assert dialogues.validate_dialogues() is True


def test_get_dialogue_by_id():
    assert dialogues.get_dialogue_by_id("d03")["title_ru"] == "Откуда ты"
    assert dialogues.get_dialogue_by_id("nope") is None


# ===== Недельный цикл =====

def test_epoch_week_zero_is_d01():
    dlg, info = dialogues.get_dialogue_for_date(dialogues.EPOCH)
    assert info["index"] == 0
    assert dlg["id"] == "d01"


def test_week_one_is_d02():
    dlg, info = dialogues.get_dialogue_for_date(dialogues.EPOCH + timedelta(days=7))
    assert info["week"] == 1
    assert dlg["id"] == "d02"


def test_before_epoch_returns_first():
    dlg, info = dialogues.get_dialogue_for_date(dialogues.EPOCH - timedelta(days=1))
    assert info["week"] == 0
    assert dlg["id"] == "d01"


def test_cycle_after_six_weeks():
    # неделя 6 -> индекс 6 % 6 = 0 -> снова d01
    dlg, info = dialogues.get_dialogue_for_date(dialogues.EPOCH + timedelta(days=42))
    assert info["week"] == 6
    assert dlg["id"] == "d01"
