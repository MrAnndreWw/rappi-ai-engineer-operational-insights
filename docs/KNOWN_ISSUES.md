# Known Issues & Blockers

## Anti-Bot Walls / Login Enforcement
**Issue:** During automated scraping runs on Rappi, the platform may intercept navigation and present a "Confirma tu identidad" (Confirm your identity) modal blocking the UI. The message asks the user to either register or log in ("Para poder seguir navegando favor de registrarte o inicia sesión").

**Cause:** Rappi triggers this anti-bot safeguard when it detects multiple store page loads, location changes, or heavy navigation within a short time from an anonymous (guest) IP browser instance.

**Resolution / Workaround:** 
The Playwright setup now supports saving and loading authentication state (`auth.json`). 
To bypass the wall permanently:
1. Run the script with the `--headed` flag and an ample timeout (or pause the script).
2. When the "Confirma tu identidad" prompt appears, manually log in with a phone number and verification code (OTP).
3. The script will automatically save your session cookies into `config/auth.json` at the end of the run.
4. Future runs (even headless ones) will automatically load `auth.json`, so Rappi will perceive the scraper as a legitimate logged-in user and typically eliminate the identity wall.
