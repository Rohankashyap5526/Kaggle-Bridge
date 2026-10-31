import asyncio

from server import _BearerAuthASGI


async def fake_app(scope, receive, send):
    await send({"type": "http.response.start", "status": 204, "headers": []})
    await send({"type": "http.response.body", "body": b""})


async def request(headers):
    app = _BearerAuthASGI(fake_app, "a" * 40)
    sent = []

    async def receive():
        return {"type": "http.request", "body": b"", "more_body": False}

    async def send(message):
        sent.append(message)

    await app(
        {"type": "http", "method": "POST", "path": "/mcp", "headers": headers},
        receive,
        send,
    )
    return sent[0]["status"]


def test_rejects_missing_token():
    assert asyncio.run(request([])) == 401


def test_rejects_wrong_token():
    assert asyncio.run(request([(b"authorization", b"Bearer wrong")])) == 401


def test_accepts_correct_token():
    assert asyncio.run(request([(b"authorization", b"Bearer " + b"a" * 40)])) == 204
