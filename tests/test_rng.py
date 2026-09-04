from coalition_formation.rng import STREAM_NAMES, RandomStreams


def test_named_streams_are_deterministic_and_independent() -> None:
    first = RandomStreams(root_seed=123, policy_seed=456)
    second = RandomStreams(root_seed=123, policy_seed=456)

    assert first.seed_manifest() == second.seed_manifest()
    assert first.seed_manifest().keys() == set(STREAM_NAMES)
    assert first.generator("scenario") is first.generator("scenario")
    assert first.generator("scenario").integers(0, 2**32, size=8).tolist() == (
        second.generator("scenario").integers(0, 2**32, size=8).tolist()
    )

    with_new_stream = RandomStreams(root_seed=123, policy_seed=456)
    with_new_stream.generator("dynamics").integers(0, 100, size=20)
    baseline = RandomStreams(root_seed=123, policy_seed=456)
    assert (
        with_new_stream.generator("scenario").integers(0, 2**32, size=8).tolist()
        == baseline.generator("scenario").integers(0, 2**32, size=8).tolist()
    )


def test_policy_seed_changes_only_the_policy_stream() -> None:
    first = RandomStreams(root_seed=123, policy_seed=1)
    second = RandomStreams(root_seed=123, policy_seed=2)

    for name in STREAM_NAMES:
        if name != "policy":
            assert first.seed_for(name) == second.seed_for(name)
    assert first.seed_for("policy") != second.seed_for("policy")
    assert first.generator("policy").integers(0, 2**32, size=8).tolist() != (
        second.generator("policy").integers(0, 2**32, size=8).tolist()
    )
