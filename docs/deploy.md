# Deploying the demo

One container runs everything: Next.js on `$PORT` (default 7860) serves the UI and forwards `/api/*`
to FastAPI on `127.0.0.1:8000`. Synthetic demo data is regenerated at every start, so the demo
resets itself and never holds real patient data.

```bash
docker build -t thodar .
docker run -p 7860:7860 thodar                      # offline demo (rules only)
docker run -p 7860:7860 -e THODAR_SARVAM_API_KEY=... thodar   # live Tamil voice notes, photo import
```

## Hugging Face Spaces (free, gives a public link for the submission)

1. Create a Space: SDK **Docker**, hardware **CPU basic**.
2. Push this repository to the Space, adding this header at the very top of the Space's README.md:
   ```yaml
   ---
   title: Thodar
   sdk: docker
   app_port: 7860
   ---
   ```
3. Optional: add `THODAR_SARVAM_API_KEY` under *Settings → Variables and secrets* (as a **secret**).

**Before making it public:** with a Sarvam key set, anyone using the demo spends your Sarvam credit
(voice notes, photo import, voice preview). Use a separate key with a small balance, or leave it
unset for an offline demo.

## Other hosts

Render, Railway or Fly.io: deploy the Dockerfile as a web service; set `PORT` if the host requires it.

## Notes

- Building the front end on Windows Git Bash: prefix with `MSYS_NO_PATHCONV=1`, otherwise
  `NEXT_PUBLIC_API_URL=/api` is rewritten to a Windows path (seen in testing).
- Production: use Postgres (`THODAR_DATABASE_URL`), a real WhatsApp Business number, and hosting in
  India (AWS Mumbai) for DPDP compliance. The demo container is for evaluation only.
