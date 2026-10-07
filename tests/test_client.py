import pytest
import requests

from tube.tfl.client import TflClient, TflError


def make(fake, *responses, key=""):
    Session, _ = fake
    session = Session(*responses)
    return TflClient(base_url="https://api.example/", app_key=key, session=session,
                     sleep=lambda s: None), session


def test_builds_url_and_adds_app_key(fake):
    _, Resp = fake
    client, session = make(fake, Resp(200, [1]), key="secret")
    assert client.get_json("/Line/Mode/tube/Status") == [1]
    call = session.calls[0]
    assert call["url"] == "https://api.example/Line/Mode/tube/Status"
    assert call["params"] == {"app_key": "secret"}


def test_no_key_means_no_key_param(fake):
    _, Resp = fake
    client, session = make(fake, Resp(200, {}))
    client.get_json("x", {"a": 1})
    assert session.calls[0]["params"] == {"a": 1}


def test_retries_once_on_429_then_succeeds(fake):
    _, Resp = fake
    client, session = make(fake, Resp(429), Resp(200, ["ok"]))
    assert client.get_json("x") == ["ok"] and len(session.calls) == 2


def test_gives_up_after_retry(fake):
    _, Resp = fake
    client, _ = make(fake, Resp(503), Resp(503))
    with pytest.raises(TflError) as e:
        client.get_json("x")
    assert e.value.status == 503


def test_404_is_not_retried(fake):
    _, Resp = fake
    client, session = make(fake, Resp(404))
    with pytest.raises(TflError):
        client.get_json("x")
    assert len(session.calls) == 1


def test_network_error_becomes_tflerror(fake):
    client, _ = make(fake, requests.ConnectionError("down"), requests.ConnectionError("down"))
    with pytest.raises(TflError, match="Could not reach TfL"):
        client.get_json("x")


def test_non_json_reply(fake):
    _, Resp = fake
    client, _ = make(fake, Resp(200, text_only=True))
    with pytest.raises(TflError, match="non-JSON"):
        client.get_json("x")
