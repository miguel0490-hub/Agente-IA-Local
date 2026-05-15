### Directorio universal de IAs

Tu SuperAgente usa el **estándar OpenAI** (REST `/v1/chat/completions`). Puedes conectar muchos proveedores con **Base URL**, **API Key** y **Model ID**.

#### Proveedores en la nube

**DeepSeek V4**
- API Keys: [platform.deepseek.com](https://platform.deepseek.com/api_keys)
- Base URL: `https://api.deepseek.com`
- Model ID: `deepseek-v4-flash`, `deepseek-v4-pro`

**Grok (xAI)**
- API Keys: [console.x.ai](https://console.x.ai/)
- Base URL: `https://api.x.ai/v1`
- Model ID: `grok-4.3`, `grok-4.20-reasoning`

**Claude (Anthropic)**
- Opción A (recomendada): motor **OpenRouter** y el Model ID de Claude.
- Opción B: API directa — [console.anthropic.com](https://console.anthropic.com/)
- Base URL: `https://api.anthropic.com/v1/`
- Model ID: `claude-sonnet-4-20250514`, `claude-haiku-4-20250514`
- API de pago; Anthropic suele ofrecer crédito inicial al registrarte.

**Perplexity (búsqueda web + IA)**
- API Keys: [perplexity.ai/settings/api](https://www.perplexity.ai/settings/api)
- Base URL: `https://api.perplexity.ai`
- Model ID: `sonar-pro`, `sonar`, `sonar-deep-research`
- API de pago; modelos Sonar con búsqueda integrada.

**Together AI / Mistral / OpenRouter**
- Base URLs: `https://api.together.xyz/v1`, `https://openrouter.ai/api/v1`
- Model ID: consulta la documentación del proveedor.

#### Proveedores locales (LM Studio / Ollama)

**Red**
Si la app está en la nube, `localhost` apunta al **servidor**, no a tu PC. Para LM Studio/Ollama expón un túnel público ([Ngrok](https://ngrok.com/), Cloudflare Tunnels) y pega la URL en **Base URL**.

**LM Studio**
- Local: `http://localhost:1234/v1`
- Online: URL pública del túnel + `/v1`
- API Key: `lm-studio`

**Ollama (modo API)**
- Local: `http://localhost:11434/v1`
- Model ID: `llama3`, `qwen2.5-coder:3b`, etc.
