import tempfile
import textwrap
import unittest

from config.loader import ConfigError, load_config


class ConfigTest(unittest.TestCase):
    def test_load_valid(self) -> None:
        content = textwrap.dedent(
            """
            user_id = "alice"
            rate_limit = 2.5

            [sync]
            mode = "api"
            """
        )
        with tempfile.NamedTemporaryFile("w", delete=False) as f:
            f.write(content)
            path = f.name
        config = load_config(path)
        self.assertEqual(config.user_id, "alice")
        self.assertEqual(config.sync.mode, "api")
        self.assertEqual(config.rate_limit, 2.5)
        self.assertTrue(config.cache.enabled)

    def test_invalid_missing_user(self) -> None:
        content = textwrap.dedent(
            """
            rate_limit = 1

            [sync]
            mode = "api"
            """
        )
        with tempfile.NamedTemporaryFile("w", delete=False) as f:
            f.write(content)
            path = f.name
        with self.assertRaises(ConfigError) as ctx:
            load_config(path)
        self.assertIn("missing 'user_id'", str(ctx.exception))
