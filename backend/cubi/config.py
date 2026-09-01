from dataclasses import dataclass


@dataclass(frozen=True)
class CubiConfig:
    """Runtime configuration for Cubi's native intelligence layer."""

    enabled: bool = True
    min_sales_for_forecast: int = 14
    forecast_horizon_days: int = 7
    anomaly_z_threshold: float = 2.5
    low_stock_horizon_days: int = 7


cubi_config = CubiConfig()
