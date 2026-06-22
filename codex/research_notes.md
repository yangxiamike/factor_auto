# Research Notes

- Sandbox v1 implementation started and the first full batch has completed.

## Batch `batch_001`

- Dataset: `datasets/sandbox_v1`
- Candidates evaluated: 30
- Passed gate: 8
- Failed gate: 22
- Invalid: 0
- Runtime errors: 0

## Observations

- Negative-direction volatility factors dominated the first passing set.
- Simple reversal signals on 3d and 5d close returns both passed on the 5d horizon.
- Several intuitive intraday and raw momentum signals validated cleanly but had near-zero directional score after preprocessing and neutralization.
- Gap continuation ideas showed some positive raw rank correlation on longer horizons, but not enough to clear the gate.

## Passing Candidates

- `fa_0005_daily_range`
- `fa_0010_volume_volatility`
- `fa_0019_reversal_3d`
- `fa_0020_reversal_5d`
- `fa_0021_daily_vol_5d`
- `fa_0022_daily_vol_10d`
- `fa_0023_range_vol_5d`
- `fa_0024_range_mean_5d`

## Next Batch Ideas

- Push deeper into reversal-volatility hybrids, especially range-based instability followed by short reversal.
- Test whether cross-sectional transforms are hurting otherwise-usable intraday signals.
- Add variants that smooth gap and volume shocks before ranking, since raw one-day versions looked noisy.
