# Copyright 2021 The Matrix.org Foundation C.I.C.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

from synapse.util.caches.response_cache import ResponseCache

from tests.server import get_clock
from tests.unittest import TestCase


class DeferredCacheTestCase(TestCase):
    """
    A TestCase class for ResponseCache.

    The test-case function naming has some logic to it in it's parts, here's some notes about it:
        wait: Denotes tests that have an element of "waiting" before its wrapped result becomes available
              (Generally these just use .delayed_return instead of .instant_return in it's wrapped call.)
        expire: Denotes tests that test expiry after assured existence.
                (These have cache with a short timeout_ms=, shorter than will be tested through advancing the clock)
    """

    def setUp(self):
        self.reactor, self.clock = get_clock()

    def with_cache(self, name: str, ms: int = 0) -> ResponseCache:
        return ResponseCache(self.clock, name, timeout_ms=ms)

    @staticmethod
    async def instant_return(o: str) -> str:
        return o

    async def delayed_return(self, o: str) -> str:
        await self.clock.sleep(1)
        return o

    def test_cache_hit(self):
        cache = self.with_cache("keeping_cache", ms=9001)

        expected_result = "howdy"

        wrap_d = cache.wrap(0, self.instant_return, expected_result)

        self.assertEqual(
            expected_result,
            self.successResultOf(wrap_d),
            "initial wrap result should be the same",
        )
        self.assertEqual(
            expected_result,
            self.successResultOf(cache.get(0)),
            "cache should have the result",
        )

    def test_cache_miss(self):
        cache = self.with_cache("trashing_cache", ms=0)

        expected_result = "howdy"

        wrap_d = cache.wrap(0, self.instant_return, expected_result)

        self.assertEqual(
            expected_result,
            self.successResultOf(wrap_d),
            "initial wrap result should be the same",
        )
        self.assertIsNone(cache.get(0), "cache should not have the result now")

    def test_cache_expire(self):
        cache = self.with_cache("short_cache", ms=1000)

        expected_result = "howdy"

        wrap_d = cache.wrap(0, self.instant_return, expected_result)

        self.assertEqual(expected_result, self.successResultOf(wrap_d))
        self.assertEqual(
            expected_result,
            self.successResultOf(cache.get(0)),
            "cache should still have the result",
        )

        # cache eviction timer is handled
        self.reactor.pump((2,))

        self.assertIsNone(cache.get(0), "cache should not have the result now")

    def test_cache_wait_hit(self):
        cache = self.with_cache("neutral_cache")

        expected_result = "howdy"

        wrap_d = cache.wrap(0, self.delayed_return, expected_result)
        self.assertNoResult(wrap_d)

        # function wakes up, returns result
        self.reactor.pump((2,))

        self.assertEqual(expected_result, self.successResultOf(wrap_d))

    def test_cache_wait_expire(self):
        cache = self.with_cache("medium_cache", ms=3000)

        expected_result = "howdy"

        wrap_d = cache.wrap(0, self.delayed_return, expected_result)
        self.assertNoResult(wrap_d)

        # stop at 1 second to callback cache eviction callLater at that time, then another to set time at 2
        self.reactor.pump((1, 1))

        self.assertEqual(expected_result, self.successResultOf(wrap_d))
        self.assertEqual(
            expected_result,
            self.successResultOf(cache.get(0)),
            "cache should still have the result",
        )

        # (1 + 1 + 2) > 3.0, cache eviction timer is handled
        self.reactor.pump((2,))

        self.assertIsNone(cache.get(0), "cache should not have the result now")