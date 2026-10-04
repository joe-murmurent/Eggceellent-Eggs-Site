import hashlib
import hmac

from django.contrib.auth.hashers import BasePasswordHasher


class LegacySHA256PasswordHasher(BasePasswordHasher):
    algorithm = "legacy_sha256"

    def encode(self, password, salt):
        digest = hashlib.sha256(password.encode()).hexdigest()
        return f"{self.algorithm}${digest}"

    def verify(self, password, encoded):
        algorithm, _, expected = encoded.partition("$")
        if algorithm != self.algorithm or len(expected) != 64:
            return False
        actual = hashlib.sha256(password.encode()).hexdigest()
        return hmac.compare_digest(actual, expected)

    def safe_summary(self, encoded):
        _, _, digest = encoded.partition("$")
        return {"algorithm": self.algorithm, "hash": digest[:6] + "..."}

    def must_update(self, encoded):
        return True
