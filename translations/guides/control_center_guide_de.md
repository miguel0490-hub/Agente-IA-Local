### Universelles IA-Verzeichnis

Ihr Agent nutzt die **OpenAI-kompatible API** (`/v1/chat/completions`). Verbinden Sie Anbieter mit **Base URL**, **API-Key** und **Model ID**.

#### Cloud-Anbieter

**DeepSeek V4**
- Keys: [platform.deepseek.com](https://platform.deepseek.com/api_keys)
- Base URL: `https://api.deepseek.com`
- Model ID: `deepseek-v4-flash`, `deepseek-v4-pro`

**Grok (xAI)**
- Keys: [console.x.ai](https://console.x.ai/)
- Base URL: `https://api.x.ai/v1`
- Model ID: `grok-4.3`, `grok-4.20-reasoning`

**Claude (Anthropic)**
- Option A (empfohlen): **OpenRouter** + Claude Model ID.
- Option B: Direkt-API — [console.anthropic.com](https://console.anthropic.com/)
- Base URL: `https://api.anthropic.com/v1/`
- Model ID: `claude-sonnet-4-20250514`, `claude-haiku-4-20250514`
- Kostenpflichtige API; oft Startguthaben.

**Perplexity (Web + LLM)**
- Keys: [perplexity.ai/settings/api](https://www.perplexity.ai/settings/api)
- Base URL: `https://api.perplexity.ai`
- Model ID: `sonar-pro`, `sonar`, `sonar-deep-research`
- Kostenpflichtig; integrierte Websuche.

**Together AI / Mistral / OpenRouter**
- Base URLs: `https://api.together.xyz/v1`, `https://openrouter.ai/api/v1`
- Model ID: siehe Dokumentation.

#### Lokal (LM Studio / Ollama)

**Netzwerk**
In der Cloud verweist `localhost` auf den **Server**, nicht auf Ihren PC. Nutzen Sie einen öffentlichen Tunnel ([Ngrok](https://ngrok.com/), Cloudflare Tunnels) und tragen Sie die URL unter **Base URL** ein.

**LM Studio**
- Lokal: `http://localhost:1234/v1`
- Cloud-App: Tunnel-URL + `/v1`
- API-Key: `lm-studio`

**Ollama (API-Modus)**
- Lokal: `http://localhost:11434/v1`
- Model ID: `llama3`, `qwen2.5-coder:3b`, usw.
