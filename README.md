# 🎬 mcptube

**Convert any YouTube video into an AI-queryable MCP server.**

YouTube URL in → searchable library → ask your AI anything about any video.

mcptube extracts transcripts, metadata, and frames from YouTube videos, indexes them into a local vector database, and exposes everything as [MCP](https://modelcontextprotocol.io/) tools — queryable by Claude, ChatGPT, VS Code Copilot, Cursor, Gemini, and any MCP-compatible client.

---

## ✨ Features

- **Semantic search** across video transcripts (single video or entire library)
- **Frame extraction** at any timestamp or by natural language query
- **Auto-classification** with LLM-generated tags
- **Illustrated reports** — single-video or cross-video, markdown or HTML
- **Video discovery** — search YouTube by topic, filter and cluster results
- **Cross-video synthesis** — themes, agreements, and contradictions across videos
- **Dual interface** — full CLI + MCP server
- **Passthrough LLM** — MCP tools require zero API keys; the client LLM does the reasoning
- **BYOK** — CLI mode supports 100+ LLM providers via LiteLLM
- **Smart video resolver** — reference videos by ID, index, or title substring

---

## 📋 Prerequisites

- **Python 3.12+**
- **ffmpeg** — required for frame extraction
  ```bash
  # macOS
  brew install ffmpeg

  # Ubuntu/Debian
  sudo apt install ffmpeg

  # Windows
  winget install ffmpeg
  ```

---

## 🚀 Installation

```bash
pip install mcptube
```

### From source (development)

```bash
git clone https://github.com/0xchamin/mcptube.git
cd mcptube
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

---

## ⚡ Quick Start

### CLI

```bash
# Add a video
mcptube add "https://www.youtube.com/watch?v=dQw4w9WgXcQ"

# List your library
mcptube list

# Search across all videos
mcptube search "machine learning basics"

# Extract a frame
mcptube frame 1 120.5

# Start the MCP server
mcptube serve
```

### MCP Server

```bash
# Streamable HTTP (default) — works with Claude Code, ChatGPT
mcptube serve

# stdio — works with VS Code, Claude Desktop, Cursor
mcptube serve --stdio
```

---

## 🔧 CLI Commands

| Command | Description |
|---------|-------------|
| `mcptube add <url>` | Ingest a YouTube video |
| `mcptube list` | List all videos in the library |
| `mcptube info <query>` | Show video details (ID, index, or text) |
| `mcptube remove <query>` | Remove a video from the library |
| `mcptube search <query>` | Semantic search across transcripts |
| `mcptube frame <video> <timestamp>` | Extract a frame at a timestamp |
| `mcptube frame-query <video> <text>` | Search transcript + extract frame |
| `mcptube classify <video>` | Auto-classify with LLM tags (BYOK) |
| `mcptube report <video>` | Generate an illustrated report (BYOK) |
| `mcptube report-query <query>` | Cross-video report from search (BYOK) |
| `mcptube discover <topic>` | Search YouTube + cluster results (BYOK) |
| `mcptube synthesize-cmd <topic> -v <id>` | Cross-video synthesis (BYOK) |
| `mcptube serve` | Start MCP server (Streamable HTTP) |
| `mcptube serve --stdio` | Start MCP server (stdio) |

### Smart Video Resolver

Commands that take a `<video>` or `<query>` argument accept:

| Input | Resolution |
|-------|-----------|
| `BpibZSMGtdY` | Exact YouTube video ID |
| `1` | Index number from `mcptube list` |
| `"prompting"` | Substring match on title or channel |

### Search Options

```bash
# Search all videos
mcptube search "attention mechanism"

# Search within a specific video
mcptube search "attention" --video "prompting"

# Limit results
mcptube search "attention" --limit 5
```

### Report Options

```bash
# Full report for a video
mcptube report "prompting" --format html --output report.html

# Focused report
mcptube report "prompting" --focus "reasoning strategies" --output focused.html

# Cross-video report from search
mcptube report-query "prompt engineering" --format html --output multi.html

# Cross-video synthesis
mcptube synthesize-cmd "prompting" -v BpibZSMGtdY -v UPGB-hsAoVY --output synthesis.html
```

---

## 🤖 MCP Tools (13 tools)

All MCP tools use the **passthrough pattern** — no API key required on the server. The connected AI client (Claude, ChatGPT, Copilot) provides the LLM reasoning.

| Tool | Description |
|------|-------------|
| `add_video(url)` | Ingest a YouTube video |
| `remove_video(video_id)` | Remove from library |
| `list_videos()` | List all videos with metadata |
| `get_info(video_id)` | Full video details with transcript |
| `search(query, video_id?, limit)` | Semantic search (single or all videos) |
| `search_library(query, tags?, limit)` | Cross-library search with tag filter |
| `get_frame(video_id, timestamp)` | Extract frame at timestamp |
| `get_frame_by_query(video_id, query)` | Search + extract frame |
| `classify_video(video_id)` | Return metadata for client classification |
| `generate_report(video_id, query?)` | Return data for client report generation |
| `generate_report_from_query(query, tags?)` | Cross-video report data |
| `discover_videos(topic)` | YouTube search results |
| `synthesize(video_ids, topic)` | Cross-video synthesis data |

---

## 🔌 MCP Client Configuration

### Claude Code

```bash
# Streamable HTTP (recommended)
claude mcp add --transport http --scope global mcptube http://127.0.0.1:9093/mcp
```

> **Note:** Use `--scope global` to make mcptube available in all projects. Without it, the server is scoped to the directory where you ran the command.

Then start the server in a separate terminal:

```bash
mcptube serve
```

### VS Code / Copilot Chat

Add to `.vscode/mcp.json` in your workspace:

```json
{
  "servers": {
    "mcptube": {
      "command": "mcptube",
      "args": ["serve", "--stdio"]
    }
  }
}
```

> **Note:** If VS Code can't find `mcptube`, use the full path to the executable:
> ```json
> "command": "/path/to/your/.venv/bin/mcptube"
> ```
> Or if installed globally via pip, the command should work as-is.

### Claude Desktop

Add to `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "mcptube": {
      "command": "mcptube",
      "args": ["serve", "--stdio"]
    }
  }
}
```

### Cursor

Add to `.cursor/mcp.json`:

```json
{
  "mcpServers": {
    "mcptube": {
      "command": "mcptube",
      "args": ["serve", "--stdio"]
    }
  }
}
```

### ChatGPT

```
Settings → Connectors → Add → http://localhost:9093/mcp
```

### Gemini CLI

Add to `settings.json`:

```json
{
  "mcpServers": {
    "mcptube": {
      "command": "mcptube",
      "args": ["serve", "--stdio"]
    }
  }
}
```

---

## 🔑 BYOK — Bring Your Own Key (CLI Mode)

CLI commands that use LLM features (classify, report, discover, synthesize) require an API key via environment variables:

```bash
# Anthropic (Claude)
export ANTHROPIC_API_KEY="sk-ant-..."

# OpenAI
export OPENAI_API_KEY="sk-..."

# Google (Gemini)
export GOOGLE_API_KEY="AI..."
```

mcptube auto-detects which key is available. Set a default model:

```bash
export MCPTUBE_DEFAULT_MODEL="anthropic/claude-sonnet-4-20250514"
```

> **Security:** Never pass API keys as CLI flags. Always use environment variables.

> **MCP mode does not need any API key** — the connected AI client provides the LLM.

---

## ⚙️ Configuration

All settings can be overridden via `MCPTUBE_`-prefixed environment variables:

| Variable | Default | Description |
|----------|---------|-------------|
| `MCPTUBE_DATA_DIR` | `~/.mcptube` | Root directory for all data |
| `MCPTUBE_HOST` | `127.0.0.1` | Server bind host |
| `MCPTUBE_PORT` | `9093` | Server bind port |
| `MCPTUBE_DEFAULT_MODEL` | `gpt-4o` | Default LLM model for CLI |

### Server Options

```bash
mcptube serve                              # Streamable HTTP on 127.0.0.1:9093
mcptube serve --stdio                      # stdio transport
mcptube serve --host 0.0.0.0 --port 8080   # Custom host/port
mcptube serve --reload                     # Dev mode with hot-reload
```

---

## 🏗️ Architecture

```
CLI (Typer)  ←──────┐
                     ├── Service Layer (McpTubeService)
MCP Server (FastMCP) ←─┘        │
                           ┌────┴────┐
                     Repository    VectorStore
                     (SQLite)      (ChromaDB)
                           │
                     Ingestion Layer
                     ├── YouTubeExtractor (yt-dlp)
                     ├── FrameExtractor (yt-dlp + ffmpeg)
                     ├── LLMClient (LiteLLM — CLI only)
                     ├── ReportBuilder (CLI only)
                     └── VideoDiscovery (CLI only)
```

### LLM Strategy

| Mode | LLM | Cost |
|------|-----|------|
| **CLI** | LiteLLM (BYOK) | User's API key |
| **MCP** | Client LLM (passthrough) | Free — client provides reasoning |

### Storage

| Component | Per video (~40 min) | 100 videos |
|-----------|-------------------|------------|
| SQLite (metadata + transcript) | ~200-500 KB | ~50 MB |
| ChromaDB (384-dim vectors) | ~1.5-2 MB | ~200 MB |
| **Total** | | **~250 MB** |

ChromaDB downloads the `all-MiniLM-L6-v2` embedding model (~80 MB) on first use. This is a one-time download cached at `~/.cache/chroma/`.

---

## 🛠️ Tech Stack

- **FastMCP 3.0** — MCP server framework (Streamable HTTP + stdio)
- **yt-dlp** — YouTube extraction (transcripts, metadata, search)
- **ffmpeg** — On-demand frame extraction
- **ChromaDB** — Local vector database with built-in embeddings
- **LiteLLM** — Unified LLM interface (100+ providers)
- **Typer** — CLI framework
- **Pydantic** — Data models and settings
- **SQLite** — Library metadata storage

---

## 🧪 Development

```bash
# Install dev dependencies
pip install -e ".[dev]"

# Run tests
pytest

# Run with coverage
pytest --cov=mcptube --cov-report=html

# Lint
ruff check src/

# Format
ruff format src/
```

---

## 📦 Project Structure

```
mcptube/
├── src/mcptube/
│   ├── __init__.py
│   ├── cli.py              # Typer CLI
│   ├── server.py           # FastMCP MCP server
│   ├── service.py          # Core business logic
│   ├── models.py           # Pydantic domain models
│   ├── config.py           # Settings (pydantic-settings)
│   ├── llm.py              # LiteLLM wrapper (BYOK)
│   ├── report.py           # ReportBuilder
│   ├── discovery.py        # VideoDiscovery
│   ├── ingestion/
│   │   ├── __init__.py
│   │   ├── youtube.py      # YouTubeExtractor
│   │   └── frames.py       # FrameExtractor
│   └── storage/
│       ├── __init__.py
│       ├── repository.py   # Abstract VideoRepository
│       ├── sqlite.py       # SQLiteVideoRepository
│       └── vectorstore.py  # VectorStore + ChromaVectorStore
├── tests/
├── pyproject.toml
└── README.md
```

---

## 🗺️ Roadmap

- [x] MVP — 13 MCP tools, CLI, semantic search, frames, reports
- [ ] MCP Apps — Interactive HTML UIs inline in chat
- [ ] Playlist / channel import
- [ ] Speaker diarization
- [ ] OCR on frames
- [ ] Auto-chaptering
- [ ] Multi-language transcripts
- [ ] SaaS tier (OAuth, pgvector, team libraries)

---

## 📄 License

MIT

---

Built with [FastMCP](https://gofastmcp.com) ⚡
