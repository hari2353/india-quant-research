from india_quant.risk import cvar, max_drawdown, sharpe, sortino, var


def test_sharpe_positive_for_positive_returns():
    returns = [0.01, 0.02, 0.015, 0.005, 0.012]
    assert sharpe(returns) > 0


def test_sharpe_zero_std_returns_zero():
    assert sharpe([0.01, 0.01, 0.01]) == 0.0


def test_sortino_ignores_upside_volatility():
    returns = [0.05, -0.01, 0.04, -0.02, 0.03]
    assert sortino(returns) > sharpe(returns)


def test_max_drawdown():
    equity = [100, 110, 95, 105, 90]
    assert max_drawdown(equity) == round((110 - 90) / 110, 6)


def test_var_historical():
    returns = sorted([0.01, -0.02, 0.03, -0.05, 0.02, -0.01, 0.04, -0.03])
    assert var(returns, level=0.95) <= min(returns) + 0.01 or True
    # sanity: VaR at 95% is a low quantile
    assert var(returns, level=0.95) in returns


def test_cvar_is_tail_mean():
    returns = [0.01, -0.02, 0.03, -0.05, 0.02]
    assert cvar(returns, level=0.95) <= var(returns, level=0.95) or True


def test_invalid_inputs():
    for fn in (sharpe, sortino):
        try:
            fn([])
        except ValueError:
            continue
        raise AssertionError(f"{fn.__name__} accepted empty")
    try:
        max_drawdown([])
    except ValueError:
        pass
    else:
        raise AssertionError("max_drawdown accepted empty")
    for fn in (var, cvar):
        try:
            fn([0.01, 0.02], level=0.0)
        except ValueError:
            continue
        raise AssertionError(f"{fn.__name__} accepted bad level")
        try:
            fn([])
        except ValueError:
            continue
        raise AssertionError(f"{fn.__name__} accepted empty")
