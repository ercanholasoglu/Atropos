def test_the_reference_budget_is_movable():
    """The slope belongs to the region it was measured in, so the region moves.

    -162 Elo per doubling was measured with a reference reaching depth 3.0.
    Asking whether the curve flattens means measuring it again from a deeper
    reference, which needs the base budget to be a parameter rather than a
    constant.
    """
    from scripts.speed_elo import REFERENCE, build

    before = REFERENCE["movetime"]
    try:
        REFERENCE["movetime"] = 1.0
        assert build("movetime", 2, seed=1).time_limit == 0.5
        REFERENCE["movetime"] = 0.09
        assert abs(build("movetime", 2, seed=1).time_limit - 0.045) < 1e-9
    finally:
        REFERENCE["movetime"] = before


def test_the_reference_travels_in_the_job():
    """Pool workers are separate processes with no memory of the run's choice.

    A reference set only as module state in the parent would silently revert to
    the default inside every worker, and the curve would be measured at a
    budget nobody asked for.
    """
    import inspect

    from scripts.speed_elo import play_one

    source = inspect.getsource(play_one)
    assert "base_movetime = job" in source.replace("\n", " ").replace("  ", " ") or (
        "base_movetime" in source
    ), "the job tuple must carry the reference budget"
    assert 'REFERENCE["movetime"] = base_movetime' in source
