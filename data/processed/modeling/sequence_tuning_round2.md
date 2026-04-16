# Sequence Tuning Round 2

Generated: 2026-03-05T11:03:12.894717

## Selected Config

- sequence_length: 8
- hidden_channels: 32
- learning_rate: 0.001
- dropout: 0.1
- epochs: 60
- batch_size: 64
- use_log_target: False
- loss: SmoothL1 (Huber beta=3.0)
- grad_clip: 1.0

## Outcome on held-out battery test split

- XGBoost RMSE: 36.978
- TCN RMSE: 33.051
- RMSE improvement vs XGBoost: 10.62%
- Backend: torch_tcn