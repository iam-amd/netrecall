# NetRecall

ISP support AI that remembers customer history before the agent picks up.

This repo now has two demo paths:

1. `index.html` is a Vercel-ready interactive web demo. It needs no API keys and is built for recruiters, judges, and quick portfolio review.
2. `netrecall/` contains the full Streamlit + FastAPI + Twilio + Groq + Hindsight implementation for the real support workflow.

## Live Web Demo

Run locally:

```bash
python -m http.server 4174
```

Open:

```text
http://localhost:4174
```

Deploy to Vercel:

```bash
vercel --prod
```

Use the repository root as the Vercel project root. The static demo is served from `index.html`.

## Full AI Demo

```bash
cd netrecall
pip install -r requirements.txt
streamlit run app.py
```

For real AI memory and phone-call behavior, copy `netrecall/.env.example` to `netrecall/.env` and fill in:

- `GROQ_API_KEY`
- `HINDSIGHT_BASE_URL`
- `HINDSIGHT_API_KEY`
- optional Twilio credentials for real calls

## What The Demo Shows

- Pre-call customer DNA with plan, equipment, area, and ticket history
- Memory ON/OFF contrast for generic vs memory-aware support
- AI co-pilot guidance with recalled evidence
- Customer transcript simulator for quick testing
- Responsive layout for desktop and mobile review
