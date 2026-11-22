"""In-memory encounter scheduling with a caller-driven clock and tick."""

from dataclasses import dataclass
from threading import Lock
from time import monotonic
from typing import Callable


@dataclass(frozen=True)
class Rule:
    boss: str
    cooldown_seconds: int

    def __post_init__(self):
        if not self.boss or type(self.cooldown_seconds) is not int or self.cooldown_seconds <= 0:
            raise ValueError("A rule needs a boss name and a positive integer cooldown")


@dataclass(frozen=True)
class Spawn:
    player: str
    scene: str
    boss: str
    generation: int


@dataclass
class Pool:
    generation: int = 0
    live: bool = False
    corpse: bool = False
    ready_at: float | None = None


class Scheduler:
    def __init__(self, rules: dict[str, Rule], clock: Callable[[], float] = monotonic):
        self._rules = dict(rules)
        self._clock = clock
        self._lock = Lock()
        self._scene: dict[str, str] = {}
        self._fighting: set[str] = set()
        self._pools: dict[tuple[str, str], Pool] = {}

    def enter(self, player: str, scene: str) -> Spawn | None:
        with self._lock:
            if self._scene.get(player) != scene:
                self._scene[player] = scene
                self._fighting.discard(player)
            return self._spawn_if_ready(player, scene, self._clock())

    def leave(self, player: str, scene: str) -> None:
        with self._lock:
            if self._scene.get(player) == scene:
                del self._scene[player]
                self._fighting.discard(player)

    def set_combat(self, player: str, scene: str, active: bool) -> None:
        with self._lock:
            if self._scene.get(player) == scene:
                if active:
                    self._fighting.add(player)
                else:
                    self._fighting.discard(player)

    def request(self, player: str, scene: str) -> Spawn | None:
        with self._lock:
            return self._spawn_if_ready(player, scene, self._clock())

    def tick(self) -> list[Spawn]:
        with self._lock:
            now = self._clock()
            spawned = []
            for player, scene in self._scene.items():
                event = self._spawn_if_ready(player, scene, now)
                if event is not None:
                    spawned.append(event)
            return spawned

    def _spawn_if_ready(self, player: str, scene: str, now: float) -> Spawn | None:
        rule = self._rules.get(scene)
        if rule is None or self._scene.get(player) != scene or player in self._fighting:
            return None
        pool = self._pools.setdefault((player, scene), Pool())
        if pool.live or pool.corpse or (pool.ready_at is not None and now < pool.ready_at):
            return None
        pool.ready_at = None
        pool.generation += 1
        pool.live = True
        return Spawn(player, scene, rule.boss, pool.generation)

    def _current_pool(self, event: Spawn) -> Pool | None:
        if self._scene.get(event.player) != event.scene:
            return None
        pool = self._pools.get((event.player, event.scene))
        if pool and pool.generation == event.generation and self._rules[event.scene].boss == event.boss:
            return pool
        return None

    def defeat(self, event: Spawn) -> bool:
        with self._lock:
            pool = self._current_pool(event)
            if pool is None or not pool.live:
                return False
            pool.live = False
            pool.corpse = True
            return True

    def clear(self, event: Spawn) -> bool:
        with self._lock:
            pool = self._current_pool(event)
            if pool is None or not pool.corpse:
                return False
            pool.corpse = False
            pool.ready_at = self._clock() + self._rules[event.scene].cooldown_seconds
            return True
