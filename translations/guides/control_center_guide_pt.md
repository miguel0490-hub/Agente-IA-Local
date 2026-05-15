### Diretório universal de IAs

O agente usa a **API compatível com OpenAI** (`/v1/chat/completions`). Ligue fornecedores com **Base URL**, **chave API** e **Model ID**.

#### Fornecedores na nuvem

**DeepSeek V4**
- Chaves: [platform.deepseek.com](https://platform.deepseek.com/api_keys)
- Base URL: `https://api.deepseek.com`
- Model ID: `deepseek-v4-flash`, `deepseek-v4-pro`

**Grok (xAI)**
- Chaves: [console.x.ai](https://console.x.ai/)
- Base URL: `https://api.x.ai/v1`
- Model ID: `grok-4.3`, `grok-4.20-reasoning`

**Claude (Anthropic)**
- Opção A (recomendada): motor **OpenRouter** + Model ID Claude.
- Opção B: API direta — [console.anthropic.com](https://console.anthropic.com/)
- Base URL: `https://api.anthropic.com/v1/`
- Model ID: `claude-sonnet-4-20250514`, `claude-haiku-4-20250514`
- API paga; crédito inicial comum.

**Perplexity (web + LLM)**
- Chaves: [perplexity.ai/settings/api](https://www.perplexity.ai/settings/api)
- Base URL: `https://api.perplexity.ai`
- Model ID: `sonar-pro`, `sonar`, `sonar-deep-research`
- API paga; pesquisa web integrada.

**Together AI / Mistral / OpenRouter**
- Base URLs: `https://api.together.xyz/v1`, `https://openrouter.ai/api/v1`
- Model ID: consulte a documentação.

#### Local (LM Studio / Ollama)

**Rede**
Se a app estiver na nuvem, `localhost` é o **servidor**, não o seu PC. Use um túnel público ([Ngrok](https://ngrok.com/), Cloudflare Tunnels) e cole o URL em **Base URL**.

**LM Studio**
- Local: `http://localhost:1234/v1`
- App na nuvem: URL do túnel + `/v1`
- Chave API: `lm-studio`

**Ollama (modo API)**
- Local: `http://localhost:11434/v1`
- Model ID: `llama3`, `qwen2.5-coder:3b`, etc.
