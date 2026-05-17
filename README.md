# Event-Driven News Sentiment Micro-API

What it is

A tiny, explainable micro-API that accepts a short text snippet (headline, release, or note) or a URL and returns a numeric sentiment score and a simple trading hint (buy / hold / sell). It uses a small rule-based lexicon and lightweight heuristics (no machine learning), so it's fast and easy to inspect.

Why this is useful

- Provides a webhook-friendly endpoint for demo trading bots, dashboards, or terminals.
- Demonstrates how keyword + numeric heuristics can produce a quick, explainable signal.
- Easy to extend: swap the lexicon, tweak thresholds, or integrate a paid model for production tiers.

Dependencies

- Python 3.7+
- Flask (tiny web framework)

Install dependency:

```bash
pip install -r requirements.txt
```

How it works (brief)

- POST JSON to /sentiment with either a text field or a url field.
- The service finds positive/negative keywords, intensifiers, and simple percent moves (e.g. "up 12%") and adds/subtracts scores.
- It normalizes the raw score into [-1, 1] and maps that to an action:
  - sentiment > 0.3 => buy
  - sentiment < -0.3 => sell
  - otherwise => hold
- The response includes a short explanation listing matched keywords and numeric clues.

How to run

Run a quick terminal demo (safe for CI / smoke tests):

```bash
python main.py
```

You should see a printed sample input and output (the script exits after the demo).

Start the server (listen on http://127.0.0.1:5000):

```bash
python main.py serve
```

Example requests

- Demo mode (no server): just run `python main.py` — output will look like:

```json
{
  "ticker": "tsla.us",
  "sentiment": 0.72,
  "action": "buy",
  "explanation": "positive keywords: beat,deliveries; intensifiers: stronger-than-expected"
}
```

- When the server is running, analyze a short text inline with curl:

```bash
curl -s -X POST http://127.0.0.1:5000/sentiment -H "Content-Type: application/json" \
  -d '{"ticker":"tsla.us","text":"Company reports stronger-than-expected deliveries and beats expectations"}'
```

Example server response (example):

```json
{"ticker":"tsla.us","sentiment":0.72,"action":"buy","explanation":"positive keywords: beat,deliveries; intensifiers: stronger-than-expected"}
```

- Analyze a URL (the server will try to extract the page <title> and meta description):

```bash
curl -s -X POST http://127.0.0.1:5000/sentiment -H "Content-Type: application/json" \
  -d '{"url":"https://example.com/some-news-article"}'
```

Notes and limitations

- This is a demo: the lexicon is tiny and heuristic-driven. For production you would use more robust NLP pipelines or paid models.
- The URL fetch tries to extract the <title> and meta description. If those are missing it falls back to a short text snippet.
- No persistent storage, rate-limiting, authentication, or robust HTML parsing are included — they are left as optional upgrades for production.

Extending the demo

- Replace the simple lexicon lists in the script with more comprehensive word/phrase lists.
- Adjust the scoring weights and thresholds in score_text().
- Add authentication and logging, or wrap this endpoint into a queued webhook system for higher-volume flows.

## How to run

```bash
pip install -r requirements.txt
python main.py
```
