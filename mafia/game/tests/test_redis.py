__all__ = (
    "TestRedisLock",
    "TestRedisState",
)


from django.test import TestCase
from fakeredis import FakeRedis

from game.redis_store import (
    acquire_game_lock,
    get_game_state,
    release_game_lock,
    set_game_state,
    update_game_state,
)


class TestRedisLock(TestCase):
    def setUp(self):
        self.fake_redis = FakeRedis(decode_responses=True)
        self._patch_redis()

    def _patch_redis(self):
        import game.redis_store

        game.redis_store.redis_client = self.fake_redis

    def test_acquire_lock_success(self):
        lock_id = acquire_game_lock("room1", timeout_sec=5)
        self.assertIsNotNone(lock_id)

    def test_acquire_lock_fails_when_locked(self):
        lock1 = acquire_game_lock("room1")
        lock2 = acquire_game_lock("room1")

        self.assertIsNotNone(lock1)
        self.assertIsNone(lock2)

    def test_release_lock_success(self):
        lock_id = acquire_game_lock("room1")
        released = release_game_lock("room1", lock_id)

        self.assertTrue(released)

    def test_release_lock_fails_with_wrong_id(self):
        acquire_game_lock("room1")
        wrong_id = "wrong-uuid"
        released = release_game_lock("room1", wrong_id)

        self.assertFalse(released)
        new_lock = acquire_game_lock("room1")
        self.assertIsNone(new_lock)


class TestRedisState(TestCase):
    def setUp(self):
        self.fake_redis = FakeRedis(decode_responses=True)
        import game.redis_store

        game.redis_store.redis_client = self.fake_redis

    def test_get_state_returns_default(self):
        state = get_game_state("room1")

        self.assertEqual(state["phase"], "lobby")
        self.assertEqual(state["round"], 0)
        self.assertEqual(state["seq"], 0)
        self.assertIsNone(state["ends_at"])

    def test_set_and_get_state(self):
        expected = {"phase": "night", "round": 1, "seq": 10, "ends_at": None}
        set_game_state("room1", expected)

        state = get_game_state("room1")
        self.assertEqual(state, expected)

    def test_update_state(self):
        set_game_state(
            "room1",
            {"phase": "day", "round": 0, "seq": 0, "ends_at": None},
        )
        update_game_state("room1", round=1, seq=5)

        state = get_game_state("room1")
        self.assertEqual(state["phase"], "day")
        self.assertEqual(state["round"], 1)
        self.assertEqual(state["seq"], 5)

    def test_state_ttl(self):
        state = {"phase": "night", "round": 1, "seq": 10, "ends_at": None}
        set_game_state("room1", state)

        key = "game:room1:state"
        ttl = self.fake_redis.ttl(key)
        self.assertGreater(ttl, 0)
