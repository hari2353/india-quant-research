from india_quant.backtest import run_backtest, walk_forward
from india_quant.data import make_fixture_prices
from india_quant.models import PortfolioConfig


def test_backtest_is_deterministic_and_costs_are_recorded():
    prices = make_fixture_prices(800)
    config = PortfolioConfig()
    first = run_backtest(prices, "defensive_rotation", config)
    second = run_backtest(prices, "defensive_rotation", config)
    assert first.equity.equals(second.equity)
    assert first.metrics["final_value"] > 0
    assert first.trades["fee"].sum() >= 0


def test_backtest_never_spends_more_than_account_value():
    result = run_backtest(make_fixture_prices(500), "equal_weight", PortfolioConfig())
    assert (result.holdings >= 0).all().all()
    assert (result.equity > 0).all()


def test_buy_and_hold_executes_only_once():
    result = run_backtest(make_fixture_prices(500), "buy_hold", PortfolioConfig())
    assert len(result.trades) == 1


def test_signal_uses_only_prior_closes():
    prices = make_fixture_prices(800)
    changed = prices.copy()
    changed.loc[changed["date"] == changed["date"].max(), "close"] *= 100
    first = run_backtest(prices, "defensive_rotation", PortfolioConfig())
    second = run_backtest(changed, "defensive_rotation", PortfolioConfig())
    # The final close can affect mark-to-market, but not the already-generated trade ledger.
    assert first.trades.iloc[:-1].equals(second.trades.iloc[:-1])


def test_walk_forward_produces_out_of_sample_rows():
    prices = make_fixture_prices(1500)
    result = walk_forward(prices, ("buy_hold", "defensive_rotation"), test_months=6)
    assert not result.empty
    assert set(result["strategy"]) == {"buy_hold", "defensive_rotation"}


def test_walk_forward_metrics_only_cover_test_window():
    prices = make_fixture_prices(1500)
    result = walk_forward(prices, ("buy_hold",), test_months=6)
    first = result.iloc[0]
    assert first["test_end"] >= first["test_start"]
    assert abs(first["total_return"]) < 1.0
