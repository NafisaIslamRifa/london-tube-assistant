# London Tube Assistant

An agentic RAG assistant for travelling on the London Underground: grounded answers from official TfL guidance, plus live line status, next trains and fares from the TfL Unified API.

> Work in progress. Built step by step with unit tests, Docker and CI.

## Run the tests
```bash
pip install -r requirements.txt
python -m pytest -q
```

## Build the knowledge base
```bash
python -m tube.ingest.fetch_tfl        # TfL guidance pages -> data/raw/tfl_pages.jsonl
python -m tube.rag.build_index         # chunk, embed, store in Chroma (data/chroma)
python -m tube.rag.retriever "Do I need to touch out on the bus?"
```

## Search with reranking, and measure it
```bash
python -m tube.rag.search --compare "Do I need to touch out on the bus?"
python -m tube.evaluation.retrieval_eval     # vector-only vs + cross-encoder, saved to eval/
```

## Ask the agent
```bash
cp .env.example .env        # add LLM_API_KEY (free at console.groq.com)
python -m tube.agent.cli "Is the Victoria line running?"
python -m tube.agent.cli    # interactive chat with follow-ups
```

## Run the web app
```bash
python -m streamlit run app/streamlit_app.py     # then open port 8501
```

## Run with Docker
```bash
cp .env.example .env                 # add LLM_API_KEY
docker compose up --build            # http://localhost:8501
```
The first start downloads the TfL pages and builds the index into a Docker volume, so later starts are instant.

| Setup | Command |
|---|---|
| Hosted LLM (Groq), default | `docker compose up --build` |
| Fully local LLM, no key (Ollama + llama3.2, ~2 GB download) | `docker compose -f docker-compose.yml -f docker-compose.ollama.yml up --build` |
| GitHub Codespaces (container networking workaround) | `docker compose -f docker-compose.yml -f docker-compose.host.yml up --build` |

## Deploy a free public demo (Streamlit Community Cloud)
1. [share.streamlit.io](https://share.streamlit.io) → **Create app** → this repo, branch `main`, file `app/streamlit_app.py`; Advanced settings → Python 3.12.
2. **Secrets**:
   ```toml
   LLM_PROVIDER = "groq"
   LLM_API_KEY = "your-groq-key"
   LLM_RPM = "4"
   DEMO_MAX_QUESTIONS = "5"
   ```
3. Deploy. The first visit builds the knowledge base (about a minute); after that it is cached.

## Live check against the TfL API
```bash
python -m scripts.fetch_stations   # builds data/stations.json
python -m scripts.smoke_tfl
```

Contains public sector information licensed under the [Open Government Licence v3.0](https://www.nationalarchives.gov.uk/doc/open-government-licence/version/3/). Powered by TfL Open Data.
