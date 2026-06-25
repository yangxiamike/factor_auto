# Data Quality Report

- dataset_path: `C:\tmp\factor_autoresearch_block2_a_line\datasets\sandbox_v1`
- dataset_id: `sandbox_v1`
- experiment_id: `csi500_ohlcv_sandbox_v1`
- overall_outcome: `warning`
- checks: `16`
- fails: `0`
- warnings: `1`

## Metrics

```json
{
  "daily_universe": {
    "dates_below_threshold": [
      "2024-01-02",
      "2024-01-03",
      "2024-01-04",
      "2024-01-05",
      "2024-01-08",
      "2024-01-09",
      "2024-01-10",
      "2024-01-11",
      "2024-01-12",
      "2024-01-15",
      "2024-01-16",
      "2024-01-17",
      "2024-01-18",
      "2024-01-19",
      "2024-01-22",
      "2024-01-23",
      "2024-01-24",
      "2024-01-25",
      "2024-01-26",
      "2024-01-29",
      "2024-01-30"
    ],
    "max": 500,
    "mean": 477.11134020618556,
    "median": 499.0,
    "min": 0,
    "threshold": 399.20000000000005
  },
  "forward_return_coverage": {
    "by_horizon": {
      "fwd_ret_1d": {
        "expected_tail_missing_rate": 1.0,
        "non_tail_coverage": 0.9997916684751,
        "non_tail_missing_rate": 0.00020833152489995748,
        "overall_coverage": 0.9954839908556217,
        "tail_date_count": 997
      },
      "fwd_ret_20d": {
        "expected_tail_missing_rate": 1.0,
        "non_tail_coverage": 0.999017779548088,
        "non_tail_missing_rate": 0.0009822204519119352,
        "overall_coverage": 0.9538113820716597,
        "tail_date_count": 10471
      },
      "fwd_ret_5d": {
        "expected_tail_missing_rate": 1.0,
        "non_tail_coverage": 0.9994833760934476,
        "non_tail_missing_rate": 0.0005166239065523673,
        "overall_coverage": 0.986555689523291,
        "tail_date_count": 2993
      }
    },
    "warning_threshold": 0.02
  },
  "market_cap_nonpositive": {
    "nonpositive_count": 0,
    "nonpositive_rate": 0.0,
    "warning_threshold": 0.0
  },
  "missing_rates": {
    "exposures": {
      "industry": 0.0,
      "market_cap": 0.0
    },
    "ohlcv": {
      "close_hfq": 0.0,
      "high_hfq": 0.0,
      "low_hfq": 0.0,
      "open_hfq": 0.0,
      "volume": 0.0
    },
    "warning_threshold": 0.05
  }
}
```

## Checks

### required_files

- outcome: `pass`
- message: all required dataset files are present
```json
{
  "files": [
    "manifest.json",
    "panel.parquet",
    "forward_returns.parquet"
  ]
}
```

### manifest_json_valid

- outcome: `pass`
- message: manifest.json is valid JSON
```json
{}
```

### manifest_required_fields

- outcome: `pass`
- message: manifest includes required contract fields
```json
{
  "fields": [
    "dataset_id",
    "experiment_id",
    "date_start",
    "date_end",
    "source",
    "source_universe_key",
    "base_filters_inherited",
    "forward_return_definition"
  ]
}
```

### manifest_config_consistency

- outcome: `pass`
- message: manifest matches config on key identity fields
```json
{
  "checked_fields": [
    "dataset_id",
    "experiment_id",
    "forward_return_definition"
  ]
}
```

### panel.parquet_required_columns

- outcome: `pass`
- message: panel.parquet includes required columns
```json
{
  "required_columns": [
    "trade_date",
    "ts_code",
    "in_universe",
    "industry",
    "market_cap",
    "open_hfq",
    "high_hfq",
    "low_hfq",
    "close_hfq",
    "volume"
  ]
}
```

### panel.parquet_trade_date_parseable

- outcome: `pass`
- message: panel.parquet trade_date values are parseable
```json
{}
```

### forward_returns.parquet_required_columns

- outcome: `pass`
- message: forward_returns.parquet includes required columns
```json
{
  "required_columns": [
    "trade_date",
    "ts_code",
    "fwd_ret_1d",
    "fwd_ret_5d",
    "fwd_ret_20d"
  ]
}
```

### forward_returns.parquet_trade_date_parseable

- outcome: `pass`
- message: forward_returns.parquet trade_date values are parseable
```json
{}
```

### panel.parquet_primary_key_unique

- outcome: `pass`
- message: panel.parquet has unique (trade_date, ts_code)
```json
{}
```

### forward_returns.parquet_primary_key_unique

- outcome: `pass`
- message: forward_returns.parquet has unique (trade_date, ts_code)
```json
{}
```

### date_range_consistency

- outcome: `pass`
- message: panel, forward returns and declared date ranges are consistent
```json
{
  "config_range": {
    "date_end": "2025-12-31",
    "date_start": "2024-01-01"
  },
  "forward_returns_range": {
    "date_end": "2025-12-31",
    "date_start": "2024-01-02"
  },
  "manifest_range": {
    "date_end": "2025-12-31",
    "date_start": "2024-01-01"
  },
  "panel_range": {
    "date_end": "2025-12-31",
    "date_start": "2024-01-02"
  }
}
```

### daily_universe_counts

- outcome: `warning`
- message: daily universe counts fall below the warning threshold on some dates
```json
{
  "dates_below_threshold": [
    "2024-01-02",
    "2024-01-03",
    "2024-01-04",
    "2024-01-05",
    "2024-01-08",
    "2024-01-09",
    "2024-01-10",
    "2024-01-11",
    "2024-01-12",
    "2024-01-15",
    "2024-01-16",
    "2024-01-17",
    "2024-01-18",
    "2024-01-19",
    "2024-01-22",
    "2024-01-23",
    "2024-01-24",
    "2024-01-25",
    "2024-01-26",
    "2024-01-29",
    "2024-01-30"
  ],
  "max": 500,
  "mean": 477.11134020618556,
  "median": 499.0,
  "min": 0,
  "threshold": 399.20000000000005
}
```

### ohlcv_missing_rates

- outcome: `pass`
- message: OHLCV missing rates are within the warning threshold
```json
{
  "missing_rates": {
    "close_hfq": 0.0,
    "high_hfq": 0.0,
    "low_hfq": 0.0,
    "open_hfq": 0.0,
    "volume": 0.0
  },
  "warning_columns": [],
  "warning_threshold": 0.05
}
```

### exposure_missing_rates

- outcome: `pass`
- message: industry and market_cap missing rates are within the warning threshold
```json
{
  "missing_rates": {
    "industry": 0.0,
    "market_cap": 0.0
  },
  "warning_columns": [],
  "warning_threshold": 0.05
}
```

### forward_return_coverage

- outcome: `pass`
- message: forward return coverage is consistent outside expected tail dates
```json
{
  "coverage": {
    "fwd_ret_1d": {
      "expected_tail_missing_rate": 1.0,
      "non_tail_coverage": 0.9997916684751,
      "non_tail_missing_rate": 0.00020833152489995748,
      "overall_coverage": 0.9954839908556217,
      "tail_date_count": 997
    },
    "fwd_ret_20d": {
      "expected_tail_missing_rate": 1.0,
      "non_tail_coverage": 0.999017779548088,
      "non_tail_missing_rate": 0.0009822204519119352,
      "overall_coverage": 0.9538113820716597,
      "tail_date_count": 10471
    },
    "fwd_ret_5d": {
      "expected_tail_missing_rate": 1.0,
      "non_tail_coverage": 0.9994833760934476,
      "non_tail_missing_rate": 0.0005166239065523673,
      "overall_coverage": 0.986555689523291,
      "tail_date_count": 2993
    }
  },
  "warning_horizons": [],
  "warning_threshold": 0.02
}
```

### market_cap_nonpositive_rate

- outcome: `pass`
- message: market_cap is positive for in-universe rows
```json
{
  "nonpositive_count": 0,
  "nonpositive_rate": 0.0,
  "warning_threshold": 0.0
}
```
