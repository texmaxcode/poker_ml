"""Trainer / `TrainingStore`: QML card keys, progress accounting, and drill bucketing."""


def test_training_store_records_drill_stats_and_load_progress_keys():
    from texasholdemgym.backend.training import TrainingStore

    st = TrainingStore()
    try:
        st.record_drill_answer("preflop", "Correct", 1.0, 0.0)
        st.record_drill_answer("flop", "Wrong", 0.0, 0.1)
        m = st.loadProgress()
        assert m["totalD"] == 2
        assert m["correctD"] == 1
        assert m["totalDecisions"] == 2
        assert m["totalCorrect"] == 1
        assert m["drillStats"]["preflop"]["totalD"] == 1
        assert m["drillStats"]["preflop"]["correctD"] == 1
        assert m["drillStats"]["flop"]["totalD"] == 1
        assert m["drillStats"]["flop"]["correctD"] == 0
        st.resetProgress()
        m2 = st.loadProgress()
        assert m2["totalD"] == 0
        assert m2["drillStats"]["river"]["totalD"] == 0
    finally:
        st.deleteLater()


def test_trainer_stub_submit_updates_accuracy_counters():
    """Stub answers must use grades/freq that `TrainingStore` counts as correct sometimes."""
    from texasholdemgym.backend.training import Trainer, TrainingStore

    store = TrainingStore()
    trainer = Trainer(store)
    try:
        trainer.submitPreflopAnswer("raise", 0.0)
        trainer.submitPreflopAnswer("fold", 0.0)
        m = store.loadProgress()
        assert m["totalD"] == 2
        assert m["correctD"] == 1
    finally:
        trainer.deleteLater()
        store.deleteLater()


def test_trainer_questions_include_svg_card_keys_for_qml():
    from texasholdemgym.backend.training import Trainer, TrainingStore

    store = TrainingStore()
    trainer = Trainer(store)
    try:
        pre = trainer.nextPreflopQuestion()
        assert pre.get("card1", "").endswith(".svg")
        assert pre.get("card2", "").endswith(".svg")

        flop = trainer.nextFlopQuestion()
        for k in ("hero1", "hero2", "board0", "board1", "board2"):
            assert flop.get(k, "").endswith(".svg")

        turn = trainer.nextTurnQuestion()
        assert turn.get("board3", "").endswith(".svg")

        river = trainer.nextRiverQuestion()
        assert river.get("board4", "").endswith(".svg")
    finally:
        trainer.deleteLater()
        store.deleteLater()


def test_record_drill_unknown_name_maps_to_preflop_bucket() -> None:
    from texasholdemgym.backend.training import TrainingStore

    st = TrainingStore()
    try:
        st.record_drill_answer("custom_drill", "Correct", 1.0, 0.0)
        m = st.loadProgress()
        assert m["drillStats"]["preflop"]["totalD"] == 1
        assert m["drillStats"]["flop"]["totalD"] == 0
    finally:
        st.deleteLater()


def test_drill_buckets_from_dict_tolerates_malformed_kv() -> None:
    from texasholdemgym.backend import training

    b = training._DrillBuckets.from_dict("not a dict")  # type: ignore[attr-defined]
    assert b.bucket("turn").totalD == 0
    b2 = training._DrillBuckets.from_dict({"turn": "bad", "river": {}})  # type: ignore[attr-defined]
    assert b2.bucket("turn").totalD == 0
