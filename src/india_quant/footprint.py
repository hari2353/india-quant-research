"""Operational footprint for backtest and research runs."""

from __future__ import annotations


def backtest_energy(cpu_hours, cpu_power_w=65.0, *, pue=1.15):
    if cpu_hours < 0 or cpu_power_w <= 0:
        raise ValueError("cpu_hours must be >= 0 and cpu_power_w > 0")
    if pue < 1.0:
        raise ValueError("pue must be >= 1.0")
    kwh = cpu_hours * cpu_power_w * pue / 1000
    return {"cpu_hours": round(cpu_hours, 4), "kwh": round(kwh, 4)}


def backtest_carbon(cpu_hours, cpu_power_w=65.0, *, carbon_intensity_g_per_kwh=400.0, pue=1.15):
    if carbon_intensity_g_per_kwh < 0:
        raise ValueError("carbon intensity must be >= 0")
    energy = backtest_energy(cpu_hours, cpu_power_w, pue=pue)
    kg = energy["kwh"] * carbon_intensity_g_per_kwh / 1000
    return {**energy, "carbon_intensity_g_per_kwh": carbon_intensity_g_per_kwh, "kgco2e": round(kg, 4)}
