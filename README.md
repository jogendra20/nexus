# NEXUS ⚡
### Unified AI Aggregation Layer — Production Deployed

[![Live](https://img.shields.io/badge/Live-Render-46E3B7?style=flat-square)](https://nexus-56tm.onrender.com)
[![Status](https://img.shields.io/badge/Status-Active-success?style=flat-square)]()
[![License](https://img.shields.io/badge/License-MIT-blue?style=flat-square)]()

NEXUS is a production-grade LLM routing and search aggregation API that unifies **10+ AI providers** under a single intelligent interface. It handles provider selection, fallback chains, search routing, and logging — so downstream systems never worry about which AI to call.

---

## 🔌 Supported Providers

### LLM Providers
| Provider | Models | Use Case |
|---|---|---|
| Groq | LLaMA 3, Mixtral | Fast inference, fallback |
| Google Gemini | Gemini 1.5 Pro/Flash | General reasoning |
| Cerebras | LLaMA 3.1 | Trading & finance queries |
| Mistral | Codestral, Mistral Large | Code generation |
| OpenRouter | 50+ models | Multi-model fallback |
| NVIDIA NIM | LLaMA, Mistral | High-performance inference |
| GitHub Models | GPT-4o, o4-mini | OpenAI-grade via student access |
| Hugging Face | FLUX, open-source LLMs | Image generation + OSS models |

### Search Providers (absorbed from DRONA)
| Provider | Mode |
|---|---|
| Tavily | Deep research |
| Serper | Fast Google results |
| You.com | Conversational search |

---

## 🧠 How Routing Works

NEXUS uses a **two-layer routing system:**

```
Incoming Request
      │
      ▼
┌─────────────────────────┐
│   Layer 1: Keyword      │  → coding → Mistral (Codestral)
│   Classification        │  → trading → Cerebras
│   (Rule-based, instant) │  → search → Search aggregator
└─────────────────────────┘
      │ (ambiguous)
      ▼
┌─────────────────────────┐
│   Layer 2: Groq         │  → classifies intent
│   Classifier            │  → routes to best provider
│   (LLM-based fallback)  │
└─────────────────────────┘
      │
      ▼
   Response
```

---

## 🚀 Features

- **Intelligent Routing** — keyword-based Layer 1 + LLM-based Layer 2 fallback
- **Multi-Provider Search** — Tavily + Serper + You.com with quota rotation
- **Image Generation** — Hugging Face (FLUX.1-schnell) → Pollinations fallback
- **Supabase Logging** — every request logged with provider, latency, tokens
- **IST Quota Resets** — daily provider quota management at midnight IST
- **Dual-Secret Auth** — secure API key authentication
- **Per-IP Rate Limiting** — abuse prevention built in
- **TTL Caching** — repeated queries served instantly
- **Telegram Alerts** — provider failures and quota warnings
- **Keep-Alive** — UptimeRobot configured, zero cold start issues

---

## 📡 API Usage

### Base URL
```
https://nexus-56tm.onrender.com
```

### LLM Completion
```bash
POST /v1/chat
Content-Type: application/json

{
  "prompt": "Explain transformer architecture",
  "mode": "auto"   # auto | coding | trading | search
}
```

### Search
```bash
POST /v1/search
Content-Type: application/json

{
  "query": "NSE announcements today",
  "mode": "deep"   # deep | fast | conversational
}
```

### Image Generation
```bash
POST /v1/image
Content-Type: application/json

{
  "prompt": "futuristic trading dashboard"
}
```

---

## 🏗️ Architecture

```
NEXUS (Core API — Render)
├── LLM Router
│   ├── Layer 1: Keyword classifier
│   └── Layer 2: Groq-based intent classifier
├── Search Aggregator (absorbed DRONA)
│   ├── Tavily
│   ├── Serper
│   └── You.com
├── Image Pipeline
│   ├── Hugging Face (FLUX.1-schnell)
│   └── Pollinations (fallback)
├── Supabase (logging + persistence)
└── Telegram Bot (alerts)
```

---

## 🔗 Ecosystem — Projects Powered by NEXUS

| Project | Description |
|---|---|
| **ARJUN** | Algorithmic trading + NSE data intelligence. Uses NEXUS for news analysis and LLM-based catalyst scoring |
| **ONYX** | AI-powered reading PWA. Uses NEXUS for summarization and content generation |
| **HUNTER** | Intraday trading framework. Uses NEXUS for pre-market analysis and Tier 1 catalyst classification |

NEXUS is the shared AI brain across all projects — one API, many consumers.

---

## 🛠️ Tech Stack

- **Backend:** Python + Flask
- **Deployment:** Render
- **Database:** Supabase (PostgreSQL)
- **Auth:** Dual-secret API key
- **Monitoring:** UptimeRobot + Telegram alerts

---

## 📊 Provider Routing Logic

| Query Type | Primary | Fallback |
|---|---|---|
| Coding / Code gen | Mistral (Codestral) | OpenRouter |
| Trading / Finance | Cerebras | Groq |
| General reasoning | Gemini | Groq |
| Search queries | Search aggregator | Tavily |
| Image generation | HuggingFace FLUX | Pollinations |
| Complex reasoning | GitHub Models (o4-mini) | OpenRouter |

---

## 📬 Contact

Built by **Joe** — indie AI builder  
For access or collaboration: open an issue or reach out via GitHub.

---

*NEXUS — One API to route them all.*

## Provider health doctor

Run the configuration inventory without making provider calls:

```bash
python doctor.py
```

Run one small health request for each configured provider. This consumes provider quota, so use it sparingly:

```bash
python doctor.py --live --json
```

The doctor reports configuration-missing, authentication, quota, model/endpoint, network, and provider failures without printing API keys or model responses.
