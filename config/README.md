# Configuration

`default.toml` contains reproducible non-secret defaults. Files in `experiments/` override only the keys needed by a baseline or ablation.

```bash
export SAFE_SDN_LLM_API_KEY=...
export SAFE_SDN_CONFIG=config/experiments/b0.toml
python main.py
```

Configuration precedence is `default.toml`, the optional experiment file, then secret environment variables. Copy `.env.example` to `.env` for local development; `.env` is never committed.
