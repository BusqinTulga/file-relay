import copy
from core.settings import DEFAULT_CONFIG
from core.security import LEGACY_DEFAULT_ADMIN_TOKEN
import unittest
from core.security import prepare_security_config, is_config_initialized
from core.utils import verify_password, hash_password

class SecurityConfigTests(unittest.TestCase):
    def test_initial_security_config_requires_setup_and_generates_jwt_secret(self):
        result = prepare_security_config(DEFAULT_CONFIG)

        self.assertTrue(result.changed)
        self.assertTrue(result.setup_required)
        self.assertEqual(result.config["admin_token"], "")
        self.assertFalse(is_config_initialized(result.config))
        self.assertGreaterEqual(len(result.config["jwt_secret"]), 32)

    def test_legacy_default_password_requires_setup(self):
        config = copy.deepcopy(DEFAULT_CONFIG)
        config["admin_token"] = hash_password(LEGACY_DEFAULT_ADMIN_TOKEN)
        config["jwt_secret"] = "j" * 48

        result = prepare_security_config(config)

        self.assertTrue(result.setup_required)
        self.assertEqual(result.config["admin_token"], "")
        self.assertEqual(result.config["jwt_secret"], "j" * 48)

    def test_custom_plaintext_password_is_hashed_and_initialized(self):
        config = copy.deepcopy(DEFAULT_CONFIG)
        config["admin_token"] = "custom-password"
        config["jwt_secret"] = "j" * 48

        result = prepare_security_config(config)

        self.assertTrue(result.password_hashed)
        self.assertTrue(is_config_initialized(result.config))
        self.assertTrue(verify_password("custom-password", result.config["admin_token"]))
