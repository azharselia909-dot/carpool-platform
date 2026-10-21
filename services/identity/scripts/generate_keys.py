from pathlib import Path

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

keys_dir = Path(__file__).resolve().parent.parent / "keys"
keys_dir.mkdir(exist_ok=True)

private_path = keys_dir / "private.pem"
public_path = keys_dir / "public.pem"

if private_path.exists():
    print("Keys already exist. Not overwriting.")
    raise SystemExit(0)

key = rsa.generate_private_key(public_exponent=65537, key_size=2048)

private_path.write_bytes(
    key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )
)
public_path.write_bytes(
    key.public_key().public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    )
)
print(f"Created {private_path} and {public_path}")