### Annuaire universel des IA

Votre agent utilise l’**API compatible OpenAI** (`/v1/chat/completions`). Connectez les fournisseurs avec **Base URL**, **clé API** et **Model ID**.

#### Fournisseurs cloud

**DeepSeek V4**
- Clés : [platform.deepseek.com](https://platform.deepseek.com/api_keys)
- Base URL : `https://api.deepseek.com`
- Model ID : `deepseek-v4-flash`, `deepseek-v4-pro`

**Grok (xAI)**
- Clés : [console.x.ai](https://console.x.ai/)
- Base URL : `https://api.x.ai/v1`
- Model ID : `grok-4.3`, `grok-4.20-reasoning`

**Claude (Anthropic)**
- Option A (recommandée) : moteur **OpenRouter** + Model ID Claude.
- Option B : API directe — [console.anthropic.com](https://console.anthropic.com/)
- Base URL : `https://api.anthropic.com/v1/`
- Model ID : `claude-sonnet-4-20250514`, `claude-haiku-4-20250514`
- API payante ; crédit d’accueil souvent disponible.

**Perplexity (web + LLM)**
- Clés : [perplexity.ai/settings/api](https://www.perplexity.ai/settings/api)
- Base URL : `https://api.perplexity.ai`
- Model ID : `sonar-pro`, `sonar`, `sonar-deep-research`
- API payante ; recherche web intégrée.

**Together AI / Mistral / OpenRouter**
- Base URLs : `https://api.together.xyz/v1`, `https://openrouter.ai/api/v1`
- Model ID : voir la documentation du fournisseur.

#### Fournisseurs locaux (LM Studio / Ollama)

**Réseau**
Si l’app est hébergée dans le cloud, `localhost` désigne le **serveur**, pas votre PC. Utilisez un tunnel public ([Ngrok](https://ngrok.com/), Cloudflare Tunnels) et collez l’URL dans **Base URL**.

**LM Studio**
- Local : `http://localhost:1234/v1`
- App cloud : URL du tunnel + `/v1`
- Clé API : `lm-studio`

**Ollama (mode API)**
- Local : `http://localhost:11434/v1`
- Model ID : `llama3`, `qwen2.5-coder:3b`, etc.
