# GraphGuesser

A competitive math game where teams try to reconstruct a secret function from sample points and hints.

## Web App (recommended for events)

### Run locally + share with teams via ngrok

```bash
pip install -r requirements.txt
python app.py
```

Then in a second terminal:
```bash
ngrok http 5000
```

Share the ngrok URL with teams. They open it in their browser to submit guesses.  
Host opens `/admin` and logs in with the admin password (default: `mathclub`).

### Deploy to Render (free, permanent URL)

1. Push this repo to GitHub.
2. Go to [render.com](https://render.com) → New Web Service → connect your repo.
3. Set these environment variables in Render:
   - `ADMIN_PASSWORD` — your chosen admin password
   - `SECRET_KEY` — any random string (e.g. `openssl rand -hex 32`)
4. Build command: `pip install -r requirements.txt`
5. Start command: `gunicorn app:app`

### Environment variables

| Variable | Default | Description |
|---|---|---|
| `ADMIN_PASSWORD` | `mathclub` | Password for the host admin panel |
| `SECRET_KEY` | `gg-dev-secret-changeme` | Flask session secret (change in production) |
| `PORT` | `5000` | Port to listen on |

## How to run a game

### Host workflow

1. Go to `/admin` and log in.
2. Click **Set Up a Game** — enter **all round functions at once** (they're hidden from teams).
3. Click **Start Game** — teams can now submit at the root URL.
4. During each round:
   - Click **Reveal Next Hint** to give teams a clue (costs them points).
   - Click **Reveal Answer & Score All** when ready — all submissions are scored and revealed simultaneously.
5. Click **Advance to Round 2** to continue.

### Team workflow

1. Open the shared URL in a browser.
2. Select your team name and type your function guess (`2*x**3 - sin(x)`, etc.).
3. Submit — your guess is stored privately, other teams can't see it.
4. Re-submit as many times as you like — only the last one counts.
5. When the host reveals, everyone's guesses and scores appear at once.

## Scoring

| Component | Formula |
|---|---|
| RMSE | `sqrt(mean((f_true(x) - f_guess(x))^2))` over 5000 points |
| Accuracy | `floor(1000 * exp(-2 * RMSE / std(f_true)))` |
| Penalty | `hints_seen_when_submitted × hint_cost` |
| Final score | `max(0, Accuracy - Penalty)` |

## Desktop GUI (original)

```bash
python gui.py
```

## CLI (original)

```bash
python main.py setup
python main.py start
python main.py hint
python main.py submit TeamName "x**2 + sin(x)"
python main.py scores
python main.py reveal
```
