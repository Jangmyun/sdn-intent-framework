# Configuration

`default.toml` contains reproducible non-secret defaults. Files in `experiments/` override only the keys needed by a baseline or ablation.

```bash
export SAFE_SDN_LLM_BASE_URL=http://127.0.0.1:11434
export SAFE_SDN_LLM_API_KEY=  # optional for unauthenticated Ollama
export SAFE_SDN_CONFIG=config/experiments/b0.toml
python main.py
```

`SAFE_SDN_LLM_BASE_URL` may be an HTTP(S) origin URL (recommended for Ollama native `/api/chat`) or an existing `/v1` compatibility URL. E1-A through E1-D all use this shared setting. The API key may be empty when the endpoint does not require authentication.

Configuration precedence is `default.toml`, the optional experiment file, then secret environment variables. Copy `.env.example` to `.env` for local development; `.env` is never committed.
