import os
import tempfile
import textwrap
import unittest
from unittest import mock

from config.loader import ConfigError, load_config


class ConfigTest(unittest.TestCase):
    def test_load_valid(self) -> None:
        content = textwrap.dedent(
            """
            [atcoder]
            user_id = "alice"

            [atcoder.sync]
            mode = "api"

            [codeforces]
            handle = "alice_cf"
            include_gym = false

            [rate_limit]
            atcoder_rps = 2.5
            codeforces_min_interval_seconds = 2.0
            """
        )
        with tempfile.NamedTemporaryFile("w", delete=False) as f:
            f.write(content)
            path = f.name
        with mock.patch.dict(
            os.environ,
            {"AC_USER_ID": "", "AC_REVEL_SESSION": "", "AC_DIFFICULTY_SOURCE_URL": ""},
            clear=False,
        ):
            config = load_config(path)
        self.assertEqual(config.atcoder.user_id, "alice")
        self.assertEqual(config.atcoder.sync.mode, "api")
        self.assertEqual(config.codeforces.handle, "alice_cf")
        self.assertEqual(config.rate_limit.atcoder_rps, 2.5)
        self.assertTrue(config.cache.enabled)

    def test_invalid_missing_user(self) -> None:
        content = textwrap.dedent(
            """
            [atcoder.sync]
            mode = "api"

            [codeforces]
            handle = "alice_cf"
            """
        )
        with tempfile.NamedTemporaryFile("w", delete=False) as f:
            f.write(content)
            path = f.name
        with mock.patch.dict(
            os.environ,
            {"AC_USER_ID": "", "AC_REVEL_SESSION": "", "AC_DIFFICULTY_SOURCE_URL": ""},
            clear=False,
        ):
            with self.assertRaises(ConfigError) as ctx:
                load_config(path)
        self.assertIn("missing 'user_id'", str(ctx.exception))
