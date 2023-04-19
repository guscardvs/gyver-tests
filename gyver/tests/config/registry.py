import contextlib
from typing import Any, Callable, Mapping, MutableMapping

from cryptography.fernet import Fernet
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from gyver.crypto.config import CryptoConfig
from gyver.crypto.rsa import RSACryptoConfig


def default_crypto_config():
    return CryptoConfig(secret=Fernet.generate_key().decode(), spares=[])


def default_rsa_config():
    private_key = rsa.generate_private_key(
        public_exponent=65537, key_size=2048, backend=default_backend()
    )
    public_key = private_key.public_key()
    return RSACryptoConfig(
        private_key=private_key.private_bytes(
            serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption(),
        ).decode(),
        public_key=public_key.public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        ).decode(),
    )


_config_map: MutableMapping[type, Callable[[], Any]] = {
    CryptoConfig: default_crypto_config,
    RSACryptoConfig: default_rsa_config,
}

with contextlib.suppress(ImportError):
    from gyver.database import DatabaseConfig
    from gyver.database.typedef import Driver

    def default_database_config():
        return DatabaseConfig(driver=Driver.SQLITE, host="/:memory")

    _config_map[DatabaseConfig] = default_database_config

config_map: Mapping[type, Callable[[], Any]] = _config_map
