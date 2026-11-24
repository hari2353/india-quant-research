from india_quant.footprint import backtest_carbon, backtest_energy


def test_energy_math():
    assert backtest_energy(10.0, 65.0, pue=1.0)["kwh"] == round(10 * 65 / 1000, 4)


def test_carbon_math():
    assert backtest_carbon(10.0, 65.0, pue=1.0, carbon_intensity_g_per_kwh=400)["kgco2e"] == round(
        10 * 65 / 1000 * 400 / 1000, 4
    )


def test_validation():
    for kwargs in (
        {"cpu_hours": -1, "cpu_power_w": 65},
        {"cpu_hours": 1, "cpu_power_w": 0},
        {"cpu_hours": 1, "cpu_power_w": 65, "pue": 0.9},
    ):
        try:
            backtest_energy(**kwargs)
        except ValueError:
            continue
        raise AssertionError(f"accepted invalid input: {kwargs}")
    try:
        backtest_carbon(1.0, 65.0, carbon_intensity_g_per_kwh=-1)
    except ValueError:
        pass
    else:
        raise AssertionError("negative carbon intensity accepted")
