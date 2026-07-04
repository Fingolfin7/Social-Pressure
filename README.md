# Social Pressure

Accountability-partner app: define a project, invite partners, log activity events,
and let mutual visibility + push notifications keep everyone on track.
See [plan.md](plan.md) for the full product plan.

## Status

MVP scaffold: data model, email/username auth, installable PWA, web push. No
project-creation/invite/logging UI yet — that's the next session.

## Run locally

```powershell
.\.venv\Scripts\Activate.ps1
python manage.py migrate
python manage.py runserver
```

Sign up at `/users/register/`. Admin at `/admin/` (create one with `createsuperuser`).

## Web push setup

VAPID keys live in `.env` (`VAPID_PRIVATE_KEY`, `VAPID_PUBLIC_KEY`, `VAPID_ADMIN_EMAIL`).
Regenerate with:

```powershell
python manage.py generate_vapid_keys
```

## Testing push on a phone

Service workers and push require a secure context (HTTPS or localhost), so plain
`http://<lan-ip>:8000` will NOT work. Two options:

1. **HTTPS tunnel** (e.g. `cloudflared tunnel --url http://localhost:8000`), then add
   the tunnel URL to `.env` as `CSRF_TRUSTED_ORIGINS=https://xyz.trycloudflare.com`
   and restart the server.
2. **Android USB**: enable USB debugging, connect, run `adb reverse tcp:8000 tcp:8000`,
   then open `http://localhost:8000` on the phone (localhost is a secure context).

Then on the phone: open the URL → sign up/log in → "Enable notifications" →
"Send test notification". Install via browser menu → "Add to Home screen".
iOS note: web push only works from the *installed* PWA (16.4+), so add to home
screen first there.
