# Dojo JWT keys (Club – Identity Provider)

The Club signs JWTs with **RS256**; the CTF validates them with the public key.

## Generate key pair

From this directory (or project root), run:

```bash
# Generate private key (keep secret)
openssl genrsa -out private.pem 2048

# Extract public key (give this to CTF platform)
openssl rsa -in private.pem -pubout -out public.pem
```

- **Club:** Keep `private.pem` here. Set `DOJO_JWT_PRIVATE_KEY_PATH` in settings to this file (default: `dojo/keys/private.pem`).
- **CTF:** Copy `public.pem` to the CTF project at `dojo_integration/keys/public.pem` (or set `DOJO_JWT_PUBLIC_KEY_PATH` / `DOJO_JWT_PUBLIC_KEY_PEM` in CTF settings).

Do not commit `private.pem` to version control. Add `dojo/keys/private.pem` to `.gitignore`.
