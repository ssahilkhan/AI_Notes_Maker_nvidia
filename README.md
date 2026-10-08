# AI Notes Maker

An AI-powered study companion built with **Streamlit** and **NVIDIA NIM (Nemotron)** models.
Chat with an academic tutor, and watch your answers automatically turn into structured,
exam-ready notes — with a live knowledge map, global search, session memory, and PDF export.

## Features

- **AI Tutor Chat** — Streaming responses from NVIDIA Nemotron models
  (`nemotron-3-super-120b`, `nemotron-3-ultra-550b`, `nemotron-3-nano-30b`) with optional
  reasoning/thinking display and a configurable academic system prompt.
- **Auto Notes Panel** — AI responses are parsed into typed sections
  (definition, formula, example, table, comparison, steps, key points, …) and upserted into
  a persistent notes document alongside the chat.
- **Knowledge Map Canvas** — An interactive Mini-Miro-style canvas: drag, pan, zoom,
  collapse and delete knowledge cards, ask the AI about a selected card (with parent/child/sibling
  context), in split or full-screen mode.
- **Session Memory** — Rolling session summaries (updated every few exchanges), important
  concept tracking, and covered-topic lists are injected back into the system prompt so the
  tutor remembers where you left off.
- **Global Search** — `Ctrl+K` unified search across chat messages, notes sections,
  knowledge nodes and doubts in *all* sessions, with jump-to-excerpt navigation.
- **PDF Export** — Export notes (with images, formulas and captured doubts) or an entire
  conversation to a styled, paginated A4 PDF via ReportLab.
- **Multi-user Accounts** — Registration/login with Argon2id password hashing
  (PBKDF2-SHA256, 600k iterations as fallback), per-user sessions, notes, settings and
  data isolation.
- **Per-user Settings** — Model choice, thinking on/off, show reasoning, temperature,
  max tokens, system prompt, panel layout — persisted per account. Users can optionally
  supply their own NVIDIA API key, which then takes precedence over the shared workspace key.
- **Uploads & Images** — Document/image uploads referenced by the notes and PDF pipeline.

## Tech Stack

| Layer     | Technology |
|-----------|------------|
| UI        | Streamlit ≥ 1.62 (custom CSS, `st.components.v1` canvas) |
| LLM       | NVIDIA NIM API (`integrate.api.nvidia.com`) via the OpenAI SDK |
| Database  | SQLite (per-user rows; path overridable with `STUDY_DB_PATH`) |
| Auth      | argon2-cffi (PBKDF2 fallback) |
| Export    | ReportLab |
| Tests     | pytest |

## Project Structure

```
AI_Notes_Maker_nvidia/
├── streamlit_app.py      # Entry point: auth gate, layout, panel wiring
├── core/                 # Backend / business logic
│   ├── auth.py           #   Registration, login, password hashing
│   ├── db.py             #   SQLite layer (users, sessions, notes, nodes, doubts…)
│   ├── nim.py            #   NVIDIA NIM client, streaming helpers, model list
│   ├── memory.py         #   Rolling summaries & concept memory
│   ├── notes.py          #   Response → typed note sections parser
│   ├── prompts.py        #   System & memory prompts
│   ├── pdf.py            #   Notes / chat PDF export
│   ├── images.py         #   Image fetching for notes & PDF
│   └── text.py           #   Text utilities (excerpts, glimpses)
├── ui/                   # Streamlit presentation layer
│   ├── layout.py         #   Page config, styles, columns, auth screen
│   ├── chat.py           #   Main chat panel
│   ├── notes.py          #   Notes rail & document panel
│   ├── canvas.py         #   Interactive knowledge map (iframe component)
│   ├── sidebar.py        #   Sessions list, settings, account footer
│   ├── search.py         #   Ctrl+K global search popover
│   ├── components.py     #   Shared widgets
│   └── context.py        #   Cross-panel context object
├── tests/                # pytest suite (auth, isolation, search, knowledge, UI flows)
├── .streamlit/           # Theme config
├── .devcontainer/        # Codespaces / dev-container setup (auto-runs the app)
└── backups/              # Archived earlier version (V1)
```

## Getting Started

### Prerequisites

- Python 3.11+
- A free NVIDIA API key — get one at
  [build.nvidia.com](https://build.nvidia.com/nvidia/nemotron-3-ultra-550b-a55b)

### Installation

```bash
git clone https://github.com/ssahilkhan/AI_Notes_Maker_nvidia.git
cd AI_Notes_Maker_nvidia

python -m venv .venv
.venv\Scripts\activate          # Windows
# source .venv/bin/activate     # macOS/Linux

pip install -r requirements.txt
```

### Configure the API key

```bash
copy .env.example .env          # Windows
# cp .env.example .env          # macOS/Linux
```

Then edit `.env`:

```env
NVIDIA_API_KEY=nvapi-YOUR_KEY_HERE
```

This is the **shared workspace key** used by every user by default. Individual users can add
their own key in the sidebar **Settings**, which then takes precedence for their responses.
The key can also be provided via `.streamlit/secrets.toml`.

### Run the app

```bash
streamlit run streamlit_app.py
```

The app opens at **http://localhost:8501**. Create an account on the auth screen, start a
study session, and chat — notes build up in the right-hand panel automatically.

### Run the tests

```bash
pip install pytest
pytest
```

The suite covers authentication, per-user data isolation, global search, knowledge-map
persistence and the main UI flows, using a throwaway database.

### Deploy on Streamlit Community Cloud (free)

This project is a long-running Streamlit server (WebSocket session protocol + SQLite on
disk), so it needs a host that runs persistent processes — serverless platforms such as
**Vercel cannot run it** (its Python runtime only loads ASGI/WSGI apps, and its functions
are stateless with ephemeral storage). Streamlit Community Cloud deploys straight from
this repository:

1. Go to [share.streamlit.io](https://share.streamlit.io) and sign in with GitHub.
2. Click **Create app** → *Deploy an existing app* → select
   `ssahilkhan/AI_Notes_Maker_nvidia`, branch `main`, entrypoint `streamlit_app.py`.
3. Open **Advanced settings → Secrets** and paste your NVIDIA API key:

   ```toml
   NVIDIA_API_KEY = "nvapi-YOUR_KEY_HERE"
   ```

   The app reads it through `st.secrets` (see `core/nim.py`); locally it falls back to
   your `.env` file.
4. Click **Deploy** — Community Cloud installs `requirements.txt` automatically and the
   first build takes a few minutes.

> **Data note:** `data/study.db` (accounts, sessions, notes) and `data/uploads/` live on
> the app container's local disk, which is not backed up and may be reset on reboot or
> redeploy. That's fine for a demo/portfolio app; for durable data, point `STUDY_DB_PATH`
> at a hosted database or migrate `core/db.py` to a managed SQL service.

> **After switching hosts:** delete or disconnect the failed Vercel project so it stops
> attempting builds on every push.

### Dev Container / Codespaces

The repo ships with a `.devcontainer` config: opening it in VS Code or GitHub Codespaces
installs dependencies and auto-starts the Streamlit server on port **8501**.

## Usage Tips

- **＋ Concept chip** under an AI answer or the **📌** button on a note section adds a card
  to the knowledge map.
- **Ctrl+K** opens global search; picking a result jumps straight to the matching message,
  note section, knowledge card or doubt.
- On the knowledge map: drag cards, `Ctrl`+wheel to zoom, double-click to collapse, and hit
  **💬 Ask** on a card to question the AI with that node's graph context.
- The sidebar footer holds account settings; changes are saved per user.

## License

No license has been specified for this repository yet.
