# VeeCasa Polly Widget Greeting Fixes — 2026-05-04

## 1. Summary

We fixed the initial widget greeting audio so it uses the same Polly/RAG `/tts` to cached `/audio/<hash>.mp3` flow as normal chat responses.

## 2. Root Problems

- Public `/tts` route was missing from NGINX on `rasa.nextlevelrnd.info`.
- `/audio` existed, but `/tts` fell through to Rasa on port `5005` and returned `404`.
- Browser autoplay with sound was blocked by Chrome when the widget auto-opened before user interaction.
- The initial `▶ Play audio` fallback prompt was confusing and prevented a clean greeting UX.
- The inside online indicator worked, but the outside launcher tab was missing its green online dot.
- The greeting text removed the `👋` emoji visually, but Polly was still playing the old cached MP3 that had spoken the emoji.
- The audio cache file lived inside the running RAG container layer, not a visible host-mounted cache path.

## 3. NGINX Fix

The production proxy fix lives on EC2 in:

`/etc/nginx/sites-available/rasa`

Notes:

- This is an EC2/NGINX reverse proxy fix, not a Rasa or RAG code fix.
- `/tts` now proxies to `http://127.0.0.1:8000/tts`.
- `/audio/` now proxies to `http://127.0.0.1:8000/audio/`.
- CORS allows `https://site.nextlevelrnd.info`.
- Production domains that should also be considered:
  - `https://veecasa.com`
  - `https://www.veecasa.com`

Verified tests:

```bash
curl -i -X POST https://rasa.nextlevelrnd.info/tts \
  -H "Content-Type: application/json" \
  -d '{"text":"Test TTS","voice":"Joanna","engine":"neural"}'
```

Expected:

- `HTTP/2 200`
- `audio.audio_url` returned

```bash
curl -I https://rasa.nextlevelrnd.info/audio/<hash>.mp3
```

Expected:

- `HTTP/2 200`
- `content-type: audio/mpeg`

## 4. Widget Fixes

`widget6.0.html` was updated to:

- Disable auto-open on page load so Chrome allows audio after the user clicks the launcher.
- Remove the initial `▶ Play audio` prompt and fallback UI.
- Keep the `▶ Continue listening` prompt.
- Increase preview limit from `10` seconds to `15` seconds.
- Remove the visible waving hand emoji from the greeting text.
- Normalize greeting behavior so the no-emoji greeting is sent to `/tts`.
- Add or restore the inside header green online status dot.
- Add the outside launcher green online status dot.
- Upgrade both green dots to a stronger live-agent glow and breathing pulse.

## 5. Chrome Autoplay Explanation

Chrome blocks unmuted audio before user interaction.

Therefore, the widget should not auto-open with sound.

Correct behavior:

`User clicks launcher -> vcOpen() -> vcGreet() -> /tts -> audio plays`

## 6. Polly Cache Issue

The old MP3 cache still contained spoken `waving hand` audio.

The `/tts` hash stayed the same because text normalization likely strips emoji before hashing.

We deleted the cached MP3 inside the running RAG container:

- Container name: `mortgage-rag-api-prod`

Command used:

```bash
docker exec -it mortgage-rag-api-prod sh -lc 'rm -f /app/audio_cache/d7dbd6df2bb1285ed91ba2e0741b30671c3a5170ed2d9b9e370734d7a248cccb.mp3'
```

Then `/tts` was retested and confirmed:

- `"cached": false`

After regeneration, the same hash file was recreated with clean no-emoji audio.

## 7. Important Future Note

The audio cache appears to live inside the container layer, not a durable host-mounted path.

Recommended follow-up: verify the docker-compose volume mapping and add or confirm:

```yaml
./audio_cache:/app/audio_cache
```

This ensures cached MP3 files survive container rebuilds and can be managed from the host.

## 8. Current Confirmed Behavior

- `/tts` returns `200`.
- `/audio` returns `200 audio/mpeg`.
- Widget no longer auto-opens.
- User click opens widget and allows greeting audio.
- Greeting uses Polly/RAG cached MP3.
- No `Play audio` prompt appears.
- `Continue listening` appears after `15` seconds.
- The waving hand emoji is no longer spoken.
- The launcher tab has a glowing green online indicator.
- The header has a glowing green online indicator.

## 9. Commit Instructions

Primary doc-only flow:

```bash
git status
git add docs/dev-handoffs/polly-widget-greeting-fixes-2026-05-04.md
git commit -m "Document Polly widget greeting fixes"
git push origin main
```

If `widget6.0.html` also has local changes that should ship with this work:

```bash
git add path/to/widget6.0.html
git commit -m "Polish Polly greeting widget behavior"
git push origin main
```