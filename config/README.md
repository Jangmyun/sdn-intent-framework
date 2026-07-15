# Configuration

`default.toml` contains reproducible non-secret defaults. Files in `experiments/` override only the keys needed by a baseline or ablation.

```bash
export SAFE_SDN_LLM_BASE_URL=http://127.0.0.1:11434/v1
export SAFE_SDN_LLM_API_KEY=  # optional for unauthenticated Ollama
export SAFE_SDN_CONFIG=config/experiments/b0.toml
python main.py
```

`SAFE_SDN_LLM_BASE_URL` must be an HTTP(S) URL whose path ends in `/v1`. The API key may be empty when the endpoint does not require authentication.

Configuration precedence is `default.toml`, the optional experiment file, then secret environment variables. Copy `.env.example` to `.env` for local development; `.env` is never committed.
