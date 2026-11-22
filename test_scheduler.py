import unittest
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

from scheduler import Rule, Scheduler, Spawn


class Clock:
    def __init__(self):
        self.seconds = 0

    def __call__(self):
        return self.seconds


class SchedulerTests(unittest.TestCase):
    def setUp(self):
        self.clock = Clock()
        self.game = Scheduler({
            "chalk-garden": Rule("paper-kite", 7),
            "tile-hill": Rule("brass-thimble", 11),
        }, self.clock)
        self.scene = "chalk-garden"

    def clear_first(self, player="visitor-a"):
        first = self.game.enter(player, self.scene)
        self.assertTrue(self.game.defeat(first))
        self.assertTrue(self.game.clear(first))
        return first

    def test_first_entry_emits_once(self):
        first = self.game.enter("visitor-a", self.scene)
        self.assertEqual(first, Spawn("visitor-a", self.scene, "paper-kite", 1))
        self.assertIsNone(self.game.enter("visitor-a", self.scene))
        self.assertIsNone(self.game.request("visitor-a", self.scene))
        self.assertEqual(self.game.tick(), [])

    def test_unconfigured_scene_is_quiet(self):
        self.assertIsNone(self.game.enter("visitor-a", "blank-sheet"))
        self.assertIsNone(self.game.request("visitor-a", self.scene))
        self.assertEqual(self.game.tick(), [])

    def test_corpse_blocks_and_cooldown_starts_on_clear(self):
        first = self.game.enter("visitor-a", self.scene)
        self.assertFalse(self.game.clear(first))
        self.assertTrue(self.game.defeat(first))
        self.clock.seconds = 18
        self.assertEqual(self.game.tick(), [])
        self.assertFalse(self.game.defeat(first))
        self.assertTrue(self.game.clear(first))
        self.clock.seconds = 24
        self.assertFalse(self.game.clear(first))
        self.assertEqual(self.game.tick(), [])
        self.clock.seconds = 25
        self.assertEqual(self.game.tick(), [Spawn("visitor-a", self.scene, "paper-kite", 2)])
        self.assertEqual(self.game.tick(), [])

    def test_combat_delays_due_encounter(self):
        self.clear_first()
        self.game.set_combat("visitor-a", self.scene, True)
        self.clock.seconds = 9
        self.assertIsNone(self.game.enter("visitor-a", self.scene))
        self.assertEqual(self.game.tick(), [])
        self.game.set_combat("visitor-a", self.scene, False)
        self.assertEqual(len(self.game.tick()), 1)

    def test_leave_preserves_cooldown_and_suppresses_absent_events(self):
        self.clear_first()
        self.game.leave("visitor-a", self.scene)
        self.clock.seconds = 3
        self.assertIsNone(self.game.enter("visitor-a", self.scene))
        self.game.leave("visitor-a", self.scene)
        self.clock.seconds = 20
        self.assertEqual(self.game.tick(), [])
        self.assertIsNone(self.game.request("visitor-a", self.scene))
        self.assertEqual(self.game.enter("visitor-a", self.scene).generation, 2)
        self.assertIsNone(self.game.enter("visitor-a", self.scene))

    def test_independent_players_and_scenes(self):
        first_a = self.clear_first()
        first_b = self.game.enter("visitor-b", self.scene)
        hill = self.game.enter("visitor-a", "tile-hill")
        self.assertEqual(hill.boss, "brass-thimble")
        self.game.leave("visitor-a", self.scene)
        self.assertFalse(self.game.clear(first_a))
        self.assertTrue(self.game.defeat(hill))
        self.assertTrue(self.game.clear(hill))
        self.clock.seconds = 7
        self.assertEqual(self.game.tick(), [])
        self.assertEqual(self.game.enter("visitor-a", self.scene).generation, 2)
        self.assertTrue(self.game.defeat(first_b))
        self.assertIsNone(self.game.enter("visitor-a", "tile-hill"))
        self.clock.seconds = 11
        self.assertEqual(self.game.tick(), [Spawn("visitor-a", "tile-hill", hill.boss, 2)])

    def test_stale_callbacks_leave_new_generation_alive(self):
        old = self.clear_first()
        self.clock.seconds = 7
        new, = self.game.tick()
        self.assertFalse(self.game.defeat(old))
        self.assertFalse(self.game.clear(old))
        self.assertTrue(self.game.defeat(new))

    def test_tick_and_request_share_one_creation(self):
        self.clear_first()
        self.clock.seconds = 7
        gate = Barrier(2)

        def request():
            gate.wait(timeout=5)
            return self.game.request("visitor-a", self.scene)

        def tick():
            gate.wait(timeout=5)
            return self.game.tick()

        with ThreadPoolExecutor(max_workers=2) as workers:
            pending = workers.submit(request)
            ticking = workers.submit(tick)
            reply = pending.result()
            events = ticking.result()
        if reply is not None:
            events.append(reply)
        self.assertEqual(events, [Spawn("visitor-a", self.scene, "paper-kite", 2)])
        self.assertEqual(self.game.tick(), [])


if __name__ == "__main__":
    unittest.main()
