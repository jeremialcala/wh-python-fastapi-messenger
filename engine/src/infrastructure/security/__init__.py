"""
    Operaciones de seguridad JWE/JWK.

    Nota: este módulo abre una conexión (lazy) a MongoDB al importarse, por lo
    que solo debe importarse cuando se necesite descifrar payloads cifrados.
"""
from .jwe import retrieve_key, encrypt_data, decrypt_data

__all__ = ["retrieve_key", "encrypt_data", "decrypt_data"]
