import pytest

from tube import bootstrap, config


@pytest.fixture
def paths(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "STATIONS_PATH", str(tmp_path / "stations.json"))
    monkeypatch.setattr(config, "RAW_DOCS_PATH", str(tmp_path / "raw" / "pages.jsonl"))
    monkeypatch.delenv("FORCE_REINDEX", raising=False)
    return tmp_path


class Recorder:
    def __init__(self, saved=11):
        self.calls, self.saved = [], saved

    def stations(self):
        self.calls.append("stations")

    def pages(self, log=print):
        self.calls.append("pages")
        return self.saved, []

    def build(self):
        self.calls.append("build")


def run(rec, count):
    return bootstrap.ensure_ready(log=lambda *a: None, fetch_stations=rec.stations,
                                  fetch_pages=rec.pages, build=rec.build, count=lambda: count)


def test_first_start_does_everything(paths):
    rec = Recorder()
    report = run(rec, count=0)
    assert rec.calls == ["stations", "pages", "build"]
    assert report == {"stations": "fetched", "index": "built"}


def test_ready_index_is_left_alone(paths):
    (paths / "stations.json").write_text("[]")
    rec = Recorder()
    assert run(rec, count=150) == {"stations": "present", "index": "present"}
    assert rec.calls == []


def test_existing_pages_are_not_downloaded_again(paths):
    (paths / "stations.json").write_text("[]")
    (paths / "raw").mkdir()
    (paths / "raw" / "pages.jsonl").write_text("{}\n")
    rec = Recorder()
    run(rec, count=0)
    assert rec.calls == ["build"]


def test_force_reindex(paths, monkeypatch):
    (paths / "stations.json").write_text("[]")
    monkeypatch.setenv("FORCE_REINDEX", "true")
    rec = Recorder()
    run(rec, count=150)
    assert rec.calls == ["pages", "build"]


def test_no_pages_downloaded_is_an_error(paths):
    (paths / "stations.json").write_text("[]")
    with pytest.raises(RuntimeError, match="Could not download"):
        run(Recorder(saved=0), count=0)


def test_fetch_all_saves_good_pages_and_reports_failures(tmp_path):
    from pathlib import Path
    from tube.ingest.fetch_tfl import fetch_all
    html = (Path(__file__).parent / "fixtures" / "tfl_page.html").read_text()

    class Resp:
        def __init__(self, ok):
            self.ok, self.text = ok, html

        def raise_for_status(self):
            if not self.ok:
                raise RuntimeError("404")

    class Session:
        def get(self, url, **kw):
            return Resp("missing" not in url)

    sources = [{"path": "/fares/a", "topic": "paying"}, {"path": "/missing", "topic": "x"}]
    saved, failed = fetch_all(tmp_path / "p.jsonl", sources, session=Session(),
                              sleep=lambda s: None, log=lambda *a: None)
    assert saved == 1 and len(failed) == 1
    assert (tmp_path / "p.jsonl").read_text().count("\n") == 1


def test_skip_bootstrap_for_ci(paths, monkeypatch):
    monkeypatch.setenv("SKIP_BOOTSTRAP", "1")
    rec = Recorder()
    assert run(rec, count=0) == {"skipped": True} and rec.calls == []
