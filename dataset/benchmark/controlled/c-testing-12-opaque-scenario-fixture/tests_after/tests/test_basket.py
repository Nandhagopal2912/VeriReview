def test_negative_quantity(run_scenario):
    assert run_scenario("negative-quantity").rejected
