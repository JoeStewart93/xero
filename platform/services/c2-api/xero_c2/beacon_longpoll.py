from __future__ import annotations

import asyncio
import uuid
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy.orm import Session
from xero_common.models import utc_now

from xero_c2.models import Beacon


class DuplicateLongPollError(RuntimeError):
    pass


@dataclass(frozen=True)
class BeaconLongPollSnapshot:
    id: str
    beacon_id: uuid.UUID
    connected_at: datetime
    last_seen: datetime


class ManagedLongPoll:
    def __init__(self, beacon_id: uuid.UUID) -> None:
        self.id = str(uuid.uuid4())
        self.beacon_id = beacon_id
        self.connected_at = utc_now()
        self.last_seen = self.connected_at
        self.pending_frame: asyncio.Future[bytes] = asyncio.get_running_loop().create_future()

    def touch(self) -> None:
        self.last_seen = utc_now()

    def snapshot(self) -> BeaconLongPollSnapshot:
        return BeaconLongPollSnapshot(
            id=self.id,
            beacon_id=self.beacon_id,
            connected_at=self.connected_at,
            last_seen=self.last_seen,
        )


class BeaconLongPollManager:
    def __init__(self) -> None:
        self._polls: dict[uuid.UUID, ManagedLongPoll] = {}
        self._lock = asyncio.Lock()

    @property
    def active_count(self) -> int:
        return len(self._polls)

    def is_active(self, beacon_id: uuid.UUID) -> bool:
        return beacon_id in self._polls

    async def register(self, beacon_id: uuid.UUID) -> ManagedLongPoll:
        poll = ManagedLongPoll(beacon_id)
        async with self._lock:
            if beacon_id in self._polls:
                raise DuplicateLongPollError("Beacon already has an active long-poll request")
            self._polls[beacon_id] = poll
        return poll

    async def unregister(self, beacon_id: uuid.UUID, poll_id: str) -> bool:
        async with self._lock:
            poll = self._polls.get(beacon_id)
            if poll is None or poll.id != poll_id:
                return False
            self._polls.pop(beacon_id, None)
        if not poll.pending_frame.done():
            poll.pending_frame.cancel()
        return True

    async def wait_for_frame(self, beacon_id: uuid.UUID, poll_id: str, *, timeout_seconds: int) -> bytes | None:
        async with self._lock:
            poll = self._polls.get(beacon_id)
            if poll is None or poll.id != poll_id:
                return None
            poll.touch()
            pending_frame = poll.pending_frame
        try:
            return await asyncio.wait_for(pending_frame, timeout=timeout_seconds)
        except (asyncio.CancelledError, TimeoutError):
            return None

    async def deliver_frame(self, beacon_id: uuid.UUID, frame: bytes) -> bool:
        async with self._lock:
            poll = self._polls.get(beacon_id)
            if poll is None or poll.pending_frame.done():
                return False
            poll.pending_frame.set_result(frame)
            poll.touch()
            return True

    async def close_all(self) -> None:
        async with self._lock:
            polls = list(self._polls.values())
            self._polls.clear()
        for poll in polls:
            if not poll.pending_frame.done():
                poll.pending_frame.cancel()

    async def snapshots(self) -> list[BeaconLongPollSnapshot]:
        async with self._lock:
            return [poll.snapshot() for poll in self._polls.values()]


def update_beacon_longpoll_state(
    session: Session,
    beacon_id: uuid.UUID,
    *,
    connected: bool,
) -> Beacon | None:
    beacon = session.get(Beacon, beacon_id)
    if beacon is None:
        return None
    beacon.transport_mode = "long-poll"
    beacon.transport_connected = connected
    beacon.transport_last_seen = utc_now()
    session.add(beacon)
    return beacon
