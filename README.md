# homebox

Utilities for interacting with the Homebox production API.

## Create an item via API

1. Export the credentials provided in the environment variables:
   - `HOMEBOX_USER` for the username or email.
   - `HOMEBOX_PASS` for the password.
2. Run the helper script:

   ```bash
   python create_homebox_item.py
   ```

The script logs in against `https://homebox.duelion.com/api`, then attempts to create a uniquely named item.
It sends browser-like headers and reuses a session to avoid Cloudflare bot challenges.
