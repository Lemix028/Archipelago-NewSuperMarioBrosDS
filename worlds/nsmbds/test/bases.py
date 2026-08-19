"""Base class for NSMBDS Archipelago automated test suite."""

from test.bases import WorldTestBase


class NSMBDSTestBase(WorldTestBase):
    game = "New Super Mario Bros. DS"

    def collect_n_by_name(self, item_name: str, count: int) -> None:
        """Collect exactly ``count`` copies instead of every matching pool item."""
        missing = count - self.count(item_name)
        if missing <= 0:
            return
        items = self.get_items_by_name(item_name)
        self.assertGreaterEqual(len(items), count)
        self.collect(items[self.count(item_name):count])
