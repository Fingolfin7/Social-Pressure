import json
import logging

from django.conf import settings
from pywebpush import WebPushException, webpush


logger = logging.getLogger(__name__)


def send_push_to_user(user, payload: dict) -> int:
    sent = 0

    for subscription in user.push_subscriptions.all():
        try:
            webpush(
                subscription_info={
                    "endpoint": subscription.endpoint,
                    "keys": {
                        "p256dh": subscription.p256dh,
                        "auth": subscription.auth,
                    },
                },
                data=json.dumps(payload),
                vapid_private_key=settings.VAPID_PRIVATE_KEY,
                vapid_claims={
                    "sub": f"mailto:{settings.VAPID_ADMIN_EMAIL}",
                },
            )
        except WebPushException as exc:
            status_code = getattr(getattr(exc, "response", None), "status_code", None)
            if status_code in {404, 410}:
                subscription.delete()
            else:
                logger.exception("Failed to send push subscription %s", subscription.pk)
            continue
        except Exception:
            logger.exception("Failed to send push subscription %s", subscription.pk)
            continue

        sent += 1

    return sent
