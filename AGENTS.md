# Agent Guidelines

- The production Homebox API URL is `https://homebox.duelion.com`, with endpoints under `/api`.
- Read the Homebox credentials from environment variables: `HOMEBOX_USER` for the username/email and `HOMEBOX_PASS` for the password. Do not hardcode credentials.
- When interacting with Homebox, always target the real production API; avoid stubs or mocks.
