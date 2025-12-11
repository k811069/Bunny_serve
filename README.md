# Bunny Server

A production-grade **LiveKit-based Voice Agent Server** designed to provide AI-powered voice conversation experiences for children. The platform features real-time voice interactions powered by Google Gemini, multiple character personalities, and extensive device integration capabilities.

## Table of Contents

- [Overview](#overview)
- [Architecture](#architecture)
- [Features](#features)
- [Project Structure](#project-structure)
- [Prerequisites](#prerequisites)
- [Installation](#installation)
- [Configuration](#configuration)
- [Running the Application](#running-the-application)
- [Docker Deployment](#docker-deployment)
- [Services & Integrations](#services--integrations)
- [Function Tools](#function-tools)
- [Monitoring & Logging](#monitoring--logging)
- [Testing](#testing)
- [API Reference](#api-reference)
- [Contributing](#contributing)
- [License](#license)

## Overview

Bunny Server consists of two main components:

1. **livekit-server** - Python-based LiveKit Agents framework running Google's Gemini Realtime AI for voice conversations
2. **mqtt-gateway** - Node.js service that bridges MQTT/UDP device communication to WebSocket for IoT device integration

The platform is designed for child-safe, engaging voice interactions with features like:
- Multiple character personalities (Bluey, Peppa Pig, Spidey, Bumblebee)
- Educational games (math, riddles, word games)
- Music and story playback
- Device control via MQTT
- Long-term conversation memory

## Architecture

```
┌─────────────────┐     ┌──────────────────┐     ┌─────────────────┐
│   IoT Device    │────▶│   MQTT Gateway   │────▶│  LiveKit Server │
│   (ESP32)       │     │   (Node.js)      │     │   (Python)      │
└─────────────────┘     └──────────────────┘     └─────────────────┘
        │                        │                        │
        │ MQTT/UDP              │ WebSocket              │ Gemini API
        │                        │                        │
        ▼                        ▼                        ▼
┌─────────────────┐     ┌──────────────────┐     ┌─────────────────┐
│  MQTT Broker    │     │  LiveKit Cloud   │     │  Google Gemini  │
└─────────────────┘     └──────────────────┘     └─────────────────┘
```

## Features

### Core Capabilities

- **Real-time Voice AI**: Native audio speech-to-speech with Google Gemini 2.5 Flash
- **Multi-Character Support**: Dynamic personality switching between child-friendly characters
- **Child Profile Personalization**: Jinja2 template rendering with age-appropriate responses
- **Function Tools**: Built-in tools for music, stories, games, and device control

### Services & Providers

| Category | Providers |
|----------|-----------|
| **STT** | Groq Whisper, Deepgram, FunASR (local) |
| **TTS** | Google Gemini (native), ElevenLabs, Edge TTS |
| **LLM** | Google Gemini (default), Groq Llama, OpenAI GPT-4 |
| **VAD** | Silero VAD, Ten VAD |
| **Memory** | Mem0, Local Memory Provider |
| **Search** | Qdrant Vector DB, Google Search |

### Content Services

- **Music Service**: Playback with language selection
- **Story Service**: Categorized stories including bedtime content
- **Game Services**: Math problems, riddles, word ladder games
- **Question Generator**: Educational question generation

## Project Structure

```
Bunny Server/
├── livekit-server/              # Main Python voice agent service
│   ├── main.py                  # Primary entrypoint
│   ├── agent.py                 # Agent configurations
│   ├── config.yaml              # Main configuration file
│   ├── .env.example             # Environment template
│   ├── requirements.txt         # Python dependencies
│   ├── pyproject.toml           # Build configuration
│   ├── src/
│   │   ├── agent/               # Core agent implementation
│   │   │   ├── main_agent.py    # Full assistant with function tools
│   │   │   ├── filtered_agent.py
│   │   │   └── error_handler.py
│   │   ├── config/              # Configuration loaders
│   │   │   ├── config_loader.py
│   │   │   └── datadog_config.py
│   │   ├── providers/           # STT/TTS/LLM providers
│   │   │   ├── provider_factory.py
│   │   │   ├── edge_tts_provider.py
│   │   │   ├── funasr_stt_provider.py
│   │   │   ├── ollama_llm_provider.py
│   │   │   └── silero_vad_provider.py
│   │   ├── services/            # Business logic services
│   │   │   ├── music_service.py
│   │   │   ├── story_service.py
│   │   │   ├── analytics_service.py
│   │   │   ├── chat_history_service.py
│   │   │   └── qdrant_semantic_search.py
│   │   ├── mcp/                 # Model Context Protocol
│   │   │   ├── mcp_client.py
│   │   │   ├── mcp_executor.py
│   │   │   └── device_control_service.py
│   │   ├── memory/              # Memory providers
│   │   │   ├── mem0_provider.py
│   │   │   └── local_memory_provider.py
│   │   ├── handlers/            # Event handlers
│   │   ├── utils/               # Utility functions
│   │   └── tools/               # Function tools
│   ├── tests/                   # Unit tests
│   └── .github/workflows/       # CI/CD pipelines
│
└── mqtt-gateway/                # Node.js bridge service
    ├── app.js                   # Main orchestration
    ├── package.json             # Node.js dependencies
    ├── Dockerfile               # Docker configuration
    ├── docker-compose.yml       # Docker Compose setup
    ├── config/                  # Configuration files
    ├── core/                    # Core modules
    ├── gateway/                 # MQTT gateway implementation
    └── audio/                   # Audio assets
```

## Prerequisites

- **Python**: 3.9 or higher
- **Node.js**: 18 or higher
- **Docker & Docker Compose**: (optional, for containerized deployment)
- **LiveKit Server**: Local or cloud instance
- **MQTT Broker**: For device communication

## Installation

### LiveKit Server (Python)

```bash
cd livekit-server

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
# or
pip install -e .
```

### MQTT Gateway (Node.js)

```bash
cd mqtt-gateway

# Install dependencies
npm install
```

## Configuration

### Environment Variables

Copy the example environment file and configure:

```bash
cp .env.example .env
```

Required environment variables:

```env
# LiveKit Configuration
LIVEKIT_URL=wss://your-livekit-server.com
LIVEKIT_API_KEY=your_api_key
LIVEKIT_API_SECRET=your_api_secret

# MQTT Configuration
MQTT_HOST=your-mqtt-broker.com
MQTT_PORT=1883

# Manager API
MANAGER_API_URL=https://your-manager-api.com
MANAGER_API_SECRET=your_secret

# AI Providers
GOOGLE_API_KEY=your_google_api_key
GROQ_API_KEY=your_groq_api_key
DEEPGRAM_API_KEY=your_deepgram_api_key
ELEVENLABS_API_KEY=your_elevenlabs_api_key

# AWS (for audio storage)
AWS_ACCESS_KEY_ID=your_aws_key
AWS_SECRET_ACCESS_KEY=your_aws_secret
AWS_S3_BUCKET=your_bucket_name

# Memory & Search
MEM0_API_KEY=your_mem0_api_key
QDRANT_URL=your_qdrant_url
QDRANT_API_KEY=your_qdrant_api_key

# Monitoring (optional)
DATADOG_API_KEY=your_datadog_api_key
LOKI_URL=your_loki_endpoint
```

### config.yaml

The main configuration file contains:

```yaml
# API Configuration
read_config_from_api: true
manager_api:
  url: "https://your-manager-api.com"
  secret: "your_secret"

# Model Configuration
models:
  llm:
    provider: "gemini"
    model: "gemini-2.5-flash-preview-native-audio-dialog"
  stt:
    provider: "groq"
    model: "whisper-large-v3-turbo"
  tts:
    provider: "google"

# Gemini Realtime Settings
gemini_realtime:
  model: "gemini-2.5-flash-preview-native-audio-dialog"
  voice: "Aoede"
  temperature: 1.8

# Agent Prompts
prompts:
  bluey: |
    You are Bluey, a friendly blue heeler puppy...
  peppa_pig: |
    You are Peppa Pig...
```

## Running the Application

### Start LiveKit Server

```bash
cd livekit-server
python main.py
```

The agent will:
1. Connect to your LiveKit server
2. Wait for incoming room connections
3. Initialize services and begin voice conversations

### Start MQTT Gateway

```bash
cd mqtt-gateway
node app.js
```

The gateway will:
1. Connect to the MQTT broker
2. Listen for device messages
3. Bridge communications to LiveKit

## Docker Deployment

### Using Docker Compose

```bash
# Start all services
docker-compose up -d

# View logs
docker-compose logs -f

# Stop services
docker-compose down
```

### MQTT Gateway Docker

```bash
cd mqtt-gateway
docker build -t bunny-mqtt-gateway .
docker run -d \
  -p 8884:8884/udp \
  -p 8004:8004 \
  --name mqtt-gateway \
  bunny-mqtt-gateway
```

### Resource Limits

The Docker setup includes:
- **CPU**: 2 cores
- **Memory**: 1GB
- **Health checks**: Every 30 seconds
- **Restart policy**: Unless stopped

## Services & Integrations

### Speech-to-Text (STT)

| Provider | Description |
|----------|-------------|
| Groq Whisper | Fast cloud-based transcription |
| Deepgram | Real-time streaming STT |
| FunASR | Local WebSocket-based STT |

### Text-to-Speech (TTS)

| Provider | Description |
|----------|-------------|
| Google Gemini | Native real-time voice synthesis |
| ElevenLabs | Premium voice cloning |
| Edge TTS | Microsoft Azure voices |

### Voice Activity Detection (VAD)

| Provider | Description |
|----------|-------------|
| Silero VAD | Offline voice activity detection |
| Ten VAD | Alternative VAD wrapper |

### External Services

- **Google Search**: Web search grounding for Gemini
- **AWS S3**: Audio file storage
- **Qdrant**: Vector embeddings and semantic search
- **Mem0**: Long-term conversation memory
- **Manager API**: Device profiles and configuration

## Function Tools

The agent supports various function tools:

### Mode Switching
```python
@function_tool
async def update_agent_mode(mode: str):
    """Switch between character modes"""
    # Modes: cheeko, math_tutor, riddle_solver, word_ladder
```

### Audio Control
```python
@function_tool
async def play_music(song_name: str, language: str = "english"):
    """Play music by name"""

@function_tool
async def play_story(story_name: str):
    """Play a story"""

@function_tool
async def stop_audio():
    """Stop current audio playback"""
```

### Device Control
```python
@function_tool
async def set_device_volume(volume: int):
    """Set device volume (0-100)"""

@function_tool
async def adjust_device_volume(direction: str):
    """Adjust volume up or down"""
```

### Games
```python
@function_tool
async def start_math_game(difficulty: str):
    """Start a math problem game"""

@function_tool
async def start_riddle_game():
    """Start a riddle game"""

@function_tool
async def start_word_ladder():
    """Start a word ladder game"""
```

## Monitoring & Logging

### Datadog Integration

APM and distributed tracing:

```python
from ddtrace import tracer

tracer.configure(
    hostname="your-datadog-agent",
    port=8126
)
```

### Grafana Loki

Centralized cloud logging:

```python
import logging_loki

handler = logging_loki.LokiHandler(
    url="https://your-loki-endpoint/loki/api/v1/push",
    tags={"application": "bunny-server"},
)
```

### Resource Monitoring

Built-in monitoring for:
- CPU usage
- Memory consumption
- Network I/O
- Thread counts
- Session duration

## Testing

### Run Tests

```bash
cd livekit-server

# Run all tests
pytest -v

# Run specific test
pytest tests/test_agent.py -v
```

### Test Coverage

```bash
pytest --cov=src --cov-report=html
```

### CI/CD Pipelines

GitHub Actions workflows:
- **tests.yml**: Unit tests on push/PR
- **ruff.yml**: Code linting and style checks
- **template-check.yml**: Configuration validation

## API Reference

### Manager API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/devices/{mac}` | GET | Get device profile |
| `/api/agents/{id}` | GET | Get agent configuration |
| `/api/children/{id}` | GET | Get child profile |
| `/api/sessions` | POST | Create new session |
| `/api/analytics` | POST | Submit analytics data |

### LiveKit Room Events

| Event | Description |
|-------|-------------|
| `participant_connected` | New participant joined |
| `participant_disconnected` | Participant left |
| `track_subscribed` | Audio track available |
| `data_received` | Data channel message |

## Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

### Code Style

- Python: Follow PEP 8, use `ruff` for linting
- Node.js: Use ESLint configuration
- Commit messages: Use conventional commits

## License

This project is proprietary software. All rights reserved.

---

## Support

For issues and feature requests, please open an issue on GitHub.

## Acknowledgments

- [LiveKit](https://livekit.io/) - Real-time communication platform
- [Google Gemini](https://deepmind.google/technologies/gemini/) - AI model
- [Anthropic Claude](https://www.anthropic.com/) - Development assistance
