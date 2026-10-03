"""Connection handling used only by the dedicated NSMBDS client.

The shared BizHawk request helpers work with this context without changing
their implementation or the contexts used by other games.
"""

from __future__ import annotations

import asyncio
import json

from worlds._bizhawk import BizHawkContext, ConnectionStatus, NotConnectedError, RequestFailedError


_VALUE_TYPES = {
    "HASH_RESPONSE": str,
    "SYSTEM_RESPONSE": str,
    "MEMORY_SIZE_RESPONSE": int,
    "READ_RESPONSE": str,
    "GUARD_RESPONSE": bool,
    "NSMBDS_FEED_MESSAGE_RESPONSE": bool,
    "NSMBDS_FEED_CONFIG_RESPONSE": bool,
    "NSMBDS_STAR_COIN_TRACKING_RESPONSE": bool,
    "NSMBDS_ITEM_WRITE_RESPONSE": bool,
}


def _validate_response(request: str, response: str) -> None:
    if request == "VERSION":
        int(response)
        return

    requests = json.loads(request)
    responses = json.loads(response)
    if not isinstance(responses, list) or len(responses) != len(requests):
        raise ValueError("Expected one response per request")
    failed_guard = None
    for req, res in zip(requests, responses):
        if not isinstance(res, dict) or not isinstance(res.get("type"), str):
            raise ValueError("Expected a response object with a type")
        response_type = res["type"]
        if response_type == "ERROR":
            if not isinstance(res.get("err"), str):
                raise ValueError("Expected an error message")
            continue
        # A failed GUARD replaces every remaining response in the batch.
        if failed_guard is not None and res == failed_guard:
            continue
        expected = {"PING": "PONG", "LOCK": "LOCKED", "UNLOCK": "UNLOCKED"}.get(
            req["type"], req["type"] + "_RESPONSE")
        if response_type != expected:
            raise ValueError(f"Expected response of type {expected} but got {response_type}")
        value_type = _VALUE_TYPES.get(response_type)
        if value_type is not None and type(res.get("value")) is not value_type:
            raise ValueError(f"Expected {response_type} with a {value_type.__name__} value")
        # Lua encodes an empty preferred-core table as [], so accept its normal
        # wire representation as well as the object used for nonempty tables.
        if response_type == "PREFERRED_CORES_RESPONSE" and (
                not isinstance(res.get("value"), dict) and res.get("value") != []):
            raise ValueError("Expected a preferred-core table")
        if response_type == "GUARD_RESPONSE" and res.get("value") is False:
            failed_guard = res


class NSMBDSBizHawkContext(BizHawkContext):
    """Keep invalid or cancelled replies out of subsequent NSMBDS requests."""

    def _discard_connection(self, streams) -> None:
        streams[1].close()
        # connect/disconnect can replace streams while an old request awaits
        # I/O. A late error must only discard that request's own connection.
        if self.streams is streams:
            self.streams = None
            self.connection_status = ConnectionStatus.NOT_CONNECTED

    async def _send_message(self, message: str) -> str:
        async with self._lock:
            if self.streams is None:
                raise NotConnectedError("You tried to send a request before a connection to BizHawk was made")
            streams = self.streams
            try:
                reader, writer = streams
                writer.write(message.encode("utf-8") + b"\n")
                await asyncio.wait_for(writer.drain(), timeout=5)
                data = await asyncio.wait_for(reader.readline(), timeout=5)
                if self.streams is not streams:
                    self._discard_connection(streams)
                    raise RequestFailedError("Connection replaced")
                if not data or not data.endswith(b"\n"):
                    self._discard_connection(streams)
                    raise RequestFailedError("Connection closed")

                response = data.decode("utf-8")
                # Validate before releasing the lock so no other request can
                # consume data from a connection already known to be invalid.
                _validate_response(message, response)
                if self.connection_status == ConnectionStatus.TENTATIVE:
                    self.connection_status = ConnectionStatus.CONNECTED
                return response
            except asyncio.CancelledError:
                # A cancelled request may still receive a reply. Close the socket
                # so that reply cannot be mistaken for the next request's reply.
                self._discard_connection(streams)
                raise
            except asyncio.TimeoutError as exc:
                self._discard_connection(streams)
                raise RequestFailedError("Connection timed out") from exc
            except OSError as exc:
                self._discard_connection(streams)
                raise RequestFailedError(f"Connection failed: {exc}") from exc
            except ValueError as exc:
                self._discard_connection(streams)
                raise RequestFailedError(f"Invalid connector response: {exc}") from exc
