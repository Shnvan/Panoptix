"""
Scaffold for mTLS mutual-TLS bootstrap. Generates a CSR and private key for the
edge gateway. In production, the CSR is signed by the control-plane CA and the
resulting cert is used for mTLS authentication.

Note: requires `pip install cryptography` (already in prod requirements).
"""

import os
import sys
from pathlib import Path

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography import x509
from cryptography.x509.oid import NameOID


def generate_key_and_csr(common_name: str, key_path: Path, csr_path: Path) -> None:
    """Generate an RSA 2048 private key and a CSR, writing both to disk."""
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)

    key_path.parent.mkdir(parents=True, exist_ok=True)
    key_path.write_bytes(
        key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.TraditionalOpenSSL,
            encryption_algorithm=serialization.NoEncryption(),
        )
    )
    key_path.chmod(0o600)

    csr = (
        x509.CertificateSigningRequestBuilder()
        .subject_name(
            x509.Name([
                x509.NameAttribute(NameOID.COMMON_NAME, common_name),
                x509.NameAttribute(NameOID.ORGANIZATION_NAME, "Panoptix Edge"),
                x509.NameAttribute(NameOID.ORGANIZATIONAL_UNIT_NAME, "Gateway"),
            ])
        )
        .sign(key, hashes.SHA256())
    )

    csr_path.write_bytes(csr.public_bytes(serialization.Encoding.PEM))
    print(f"Generated key and CSR for {common_name}")


def load_or_generate(common_name: str, key_path: Path, csr_path: Path) -> bool:
    """Return False if already bootstrapped; otherwise generate and return True."""
    if key_path.exists() and csr_path.exists():
        return False
    generate_key_and_csr(common_name, key_path, csr_path)
    return True


if __name__ == "__main__":
    cn = os.environ.get("PANOPTIX_GATEWAY_ID", "gateway-dev")
    bootstrapped = load_or_generate(
        common_name=cn,
        key_path=Path("certs/gateway.key"),
        csr_path=Path("certs/gateway.csr"),
    )
    sys.exit(0 if not bootstrapped else 0)
