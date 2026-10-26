# Newton Logistics demo

A Flask + SQLite shipment tracking app with:
- Public tracking by code
- Private admin login
- Create shipments with generated or manually entered tracking codes
- Update status and last confirmed location
- Persistent SQLite database

## Run locally in Termux
```bash
pkg update -y
pkg install python -y
pip install flask
export APP_SECRET="$(python -c 'import secrets; print(secrets.token_hex(32))')"
export ADMIN_PASSWORD='choose-a-long-unique-password'
python app.py
```
Open `http://127.0.0.1:5000` on the same phone. Admin dashboard: `/login`.

## Before public deployment
1. Set a strong, unique `ADMIN_PASSWORD`.
2. Set a random `APP_SECRET`.
3. Use a persistent disk/volume for `shipments.db`; ephemeral hosting may erase it.
4. Deploy with a production WSGI server (e.g. gunicorn) and HTTPS.
5. Back up the database. Do not use default secrets or passwords.
6. Enter only real, verified shipment details; this app does not have live GPS or carrier integrations.

For a hosted service, set the start command to `gunicorn app:app` and install `gunicorn` alongside Flask. Configure the host's persistent storage for the directory containing `shipments.db`.
