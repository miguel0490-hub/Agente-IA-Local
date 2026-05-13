### Universal AI directory

Your agent uses the **OpenAI-compatible API** (`/v1/chat/completions`). Connect providers with **Base URL**, **API key**, and **Model ID**.

#### Cloud providers

**DeepSeek V4**
- API keys: [platform.deepseek.com](https://platform.deepseek.com/api_keys)
- Base URL: `https://api.deepseek.com`
- Model ID: `deepseek-v4-flash`, `deepseek-v4-pro`

**Grok (xAI)**
- API keys: [console.x.ai](https://console.x.ai/)
- Base URL: `https://api.x.ai/v1`
- Model ID: `grok-4.3`, `grok-4.20-reasoning`

**Claude (Anthropic)**
- Option A (recommended): **OpenRouter** engine + Claude model ID.
- Option B: direct API — [console.anthropic.com](https://console.anthropic.com/)
- Base URL: `https://api.anthropic.com/v1/`
- Model ID: `claude-sonnet-4-20250514`, `claude-haiku-4-20250514`
- Paid API; Anthropic often gives starter credit.

**Perplexity (web + LLM)**
- API keys: [perplexity.ai/settings/api](https://www.perplexity.ai/settings/api)
- Base URL: `https://api.perplexity.ai`
- Model ID: `sonar-pro`, `sonar`, `sonar-deep-research`
- Paid API; Sonar models include web search.

**Together AI / Mistral / OpenRouter**
- Base URLs: `https://api.together.xyz/v1`, `https://openrouter.ai/api/v1`
- Model ID: see your provider’s docs.

#### Local providers (LM Studio / Ollama)

**Networking**
If the app runs in the cloud, `localhost` is the **server**, not your machine. Use a public tunnel (e.g. [Ngrok](https://ngrok.com/), Cloudflare Tunnels) and paste the URL into **Base URL**.

**LM Studio**
- Local: `http://localhost:1234/v1`
- Cloud app: your tunnel URL + `/v1`
- API key: `lm-studio`

**Ollama (API mode)**
- Local: `http://localhost:11434/v1`
- Model ID: `llama3`, `qwen2.5-coder:3b`, etc.
