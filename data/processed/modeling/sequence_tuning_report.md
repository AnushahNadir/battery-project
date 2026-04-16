# Sequence Model Tuning Report

Generated: 2026-03-04T17:07:05.730295
Backend: `tcn`

## Best Config (by test_probe_rmse)

- sequence_length: 16
- hidden_channels: 64
- learning_rate: 0.002
- dropout: 0.15

## Performance

- Best validation RMSE: 15.330
- Best test-probe RMSE: 31.871
- Final test RMSE: 38.999
- Final test MAE: 27.290
- Final backend: torch_tcn

## Notes

- Selection used battery-level inner train/validation split.
- Final model was retrained on full train batteries and evaluated on held-out test batteries.