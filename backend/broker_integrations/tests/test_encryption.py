import os

from cryptography.fernet import Fernet
from django.test import TestCase

from broker_integrations.services.encryption import decrypt, encrypt


class EncryptionTests(TestCase):
    def test_encrypt_and_decrypt_roundtrip(self):
        os.environ["BROKER_ENCRYPTION_KEY"] = Fernet.generate_key().decode()
        encrypted = encrypt("hello")
        self.assertNotEqual(encrypted, b"hello")
        self.assertEqual(decrypt(encrypted), "hello")
