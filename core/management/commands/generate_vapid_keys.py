import base64

from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat
from django.conf import settings
from django.core.management.base import BaseCommand
from py_vapid import Vapid


def base64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode("ascii").rstrip("=")


def generate_keys():
    vapid = Vapid()
    vapid.generate_keys()

    private_number = vapid.private_key.private_numbers().private_value
    private_raw = private_number.to_bytes(32, "big")
    public_raw = vapid.public_key.public_bytes(
        Encoding.X962,
        PublicFormat.UncompressedPoint,
    )

    return base64url(private_raw), base64url(public_raw)


def env_has_key(env_text, key):
    return any(
        line.strip().startswith(f"{key}=")
        for line in env_text.splitlines()
    )


class Command(BaseCommand):
    help = "Generate VAPID keys for browser web push."

    def handle(self, *args, **options):
        private_key, public_key = generate_keys()
        lines = [
            f"VAPID_PRIVATE_KEY={private_key}",
            f"VAPID_PUBLIC_KEY={public_key}",
            "VAPID_ADMIN_EMAIL=admin@example.com",
        ]

        for line in lines:
            self.stdout.write(line)

        env_path = settings.BASE_DIR / ".env"
        if not env_path.exists():
            return

        env_text = env_path.read_text(encoding="utf-8")
        missing = [
            line
            for line in lines
            if not env_has_key(env_text, line.split("=", 1)[0])
        ]
        if not missing:
            return

        prefix = "" if env_text.endswith(("\n", "\r")) else "\n"
        env_path.write_text(
            f"{env_text}{prefix}{chr(10).join(missing)}\n",
            encoding="utf-8",
        )
        self.stdout.write(self.style.SUCCESS("Appended missing VAPID keys to .env."))
