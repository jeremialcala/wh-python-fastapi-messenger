# -*- coding: utf-8 -*-
import json


class BodySizeLimit:
    """
        Turns away a request whose body is larger than the limit, before the application sees any of it: no
        signature is checked, no token opened and nothing parsed for a body nobody should be sending.

        The body is read here, up to the limit, and handed on whole. A request that says how long it is and is
        too long is answered without reading it.
    """

    def __init__(self, app, limit: int):
        self.app = app
        self.limit = limit

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        declared = dict(scope["headers"]).get(b"content-length", b"0")
        if not declared.isdigit() or int(declared) > self.limit:
            await self._too_large(send)
            return

        chunks, size, more = [], 0, True
        while more:
            message = await receive()
            if message["type"] != "http.request":
                # The caller went away before sending it all.
                return
            chunk = message.get("body", b"")
            size += len(chunk)
            if size > self.limit:
                await self._too_large(send)
                return
            chunks.append(chunk)
            more = message.get("more_body", False)

        pending = [{"type": "http.request", "body": b"".join(chunks), "more_body": False}]

        async def whole():
            return pending.pop() if pending else await receive()

        await self.app(scope, whole, send)

    @staticmethod
    async def _too_large(send):
        body = json.dumps({"code": 413, "message": "PAYLOAD TOO LARGE"}).encode()
        await send({"type": "http.response.start", "status": 413,
                    "headers": [(b"content-type", b"application/json"),
                                (b"content-length", str(len(body)).encode()), (b"connection", b"close")]})
        await send({"type": "http.response.body", "body": body})
