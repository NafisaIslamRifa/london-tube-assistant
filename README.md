# London Tube Assistant

An agentic RAG assistant for travelling on the London Underground: grounded answers from official TfL guidance, plus live line status, next trains and fares from the TfL Unified API.

> Work in progress. Built step by step with unit tests, Docker and CI.

## Run the tests
```bash
pip install -r requirements.txt
python -m pytest -q
```

## Live check against the TfL API
```bash
python -m scripts.fetch_stations   # builds data/stations.json
python -m scripts.smoke_tfl
```

Contains public sector information licensed under the [Open Government Licence v3.0](https://www.nationalarchives.gov.uk/doc/open-government-licence/version/3/). Powered by TfL Open Data.
