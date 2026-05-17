from flask import Flask, request, jsonify
import re
import math
import urllib.request
import urllib.error
import html
import sys
import json

app = Flask(__name__)

# Lightweight lexicon and simple heuristics
POSITIVE = [
    "beat expectations", "beats expectations", "beat", "beats", "strong", "stronger", "upgrade", "outperform", "growth",
    "record", "surge", "rise", "gain", "positive", "better", "deliveries", "soared"
]
NEGATIVE = [
    "miss expectations", "missed expectations", "miss", "misses", "weak", "weaker", "downgrade", "underperform", "decline",
    "drop", "fall", "loss", "negative", "recall", "lawsuit", "cut", "missed", "poor"
]
INTENSIFIERS = ["stronger-than-expected", "better-than-expected", "significant", "sharply", "dramatically"]

# helper to find phrase matches (multi-word aware)
def find_matches(text, keywords):
    found = []
    t = text.lower()
    for kw in keywords:
        if kw in t:
            found.append(kw)
    return found

# parse simple percentage moves like 'up 12%' or 'down 3%'
def extract_percent_moves(text):
    moves = []
    # patterns: up|rose|increased 12% OR down|fell|declined 3%
    up_pat = re.compile(r"(?:\bup\b|\brose\b|\bincreased\b|\bgained\b)\s+(\d{1,3})%")
    down_pat = re.compile(r"(?:\bdown\b|\bfell\b|\bdeclined\b|\blost\b)\s+(\d{1,3})%")
    for m in up_pat.finditer(text.lower()):
        try:
            moves.append(("up", int(m.group(1))))
        except Exception:
            pass
    for m in down_pat.finditer(text.lower()):
        try:
            moves.append(("down", int(m.group(1))))
        except Exception:
            pass
    return moves

# build a compact human explanation
def build_explanation(positives, negatives, intensifiers, percents):
    parts = []
    if positives:
        parts.append("positive keywords: " + ",".join(positives))
    if negatives:
        parts.append("negative keywords: " + ",".join(negatives))
    if intensifiers:
        parts.append("intensifiers: " + ",".join(intensifiers))
    if percents:
        pct_parts = [f"{d} {p}%" for d, p in percents]
        parts.append("moves: " + ",".join(pct_parts))
    if not parts:
        return "no clear keyword matches"
    return "; ".join(parts)

# core scoring: returns float in [-1,1] and explanation pieces
def score_text(text):
    text_l = text.lower()
    pos = find_matches(text, POSITIVE)
    neg = find_matches(text, NEGATIVE)
    ints = find_matches(text, INTENSIFIERS)
    percents = extract_percent_moves(text)

    # raw score starts at 0
    score = 0.0
    # each positive word: +1
    score += len(pos) * 1.0
    # each negative word: -1
    score -= len(neg) * 1.0
    # intensifiers add 0.7 each
    score += len(ints) * 0.7
    # percent moves scale: up by p% adds p/10, down subtracts
    for dirc, p in percents:
        if dirc == "up":
            score += (p / 10.0)
        else:
            score -= (p / 10.0)

    # small heuristic: presence of words like 'guidance' or 'profit' nudges polarity
    if "guidance" in text_l and "raise" in text_l:
        score += 0.8
    if "guidance" in text_l and "cut" in text_l:
        score -= 0.8

    # normalize into (-1,1) smoothly using tanh, with small scale to keep sensitivity
    sentiment = math.tanh(score / 2.0)
    # round for API friendliness
    sentiment_rounded = round(sentiment, 2)

    explanation = build_explanation(pos, neg, ints, percents)
    return sentiment_rounded, explanation

# fetch URL and try to extract title and meta description
def fetch_text_from_url(url, timeout=6):
    try:
        resp = urllib.request.urlopen(url, timeout=timeout)
        b = resp.read(200000)  # cap to 200KB
        try:
            s = b.decode('utf-8')
        except Exception:
            try:
                s = b.decode('latin-1')
            except Exception:
                s = ''
        # unescape html entities
        s = html.unescape(s)
        # extract title
        title_m = re.search(r'<title>(.*?)</title>', s, re.IGNORECASE | re.DOTALL)
        title = title_m.group(1).strip() if title_m else ''
        # meta description (more permissive)
        meta_m = re.search(r'<meta\s+[^>]*(?:name|property)=["\']?(?:description|og:description)["\']?[^>]*content=["\'](.*?)["\']', s, re.IGNORECASE | re.DOTALL)
        meta = meta_m.group(1).strip() if meta_m else ''
        # fallback: strip tags and take leading text
        if not title and not meta:
            # remove scripts/styles
            text_only = re.sub(r'<(script|style).*?>.*?</\1>', ' ', s, flags=re.IGNORECASE | re.DOTALL)
            text_only = re.sub(r'<[^>]+>', ' ', text_only)
            text_only = re.sub(r'\s+', ' ', text_only).strip()
            snippet = text_only[:500]
            return snippet
        return (title + ' ' + meta).strip()
    except urllib.error.URLError as e:
        raise
    except Exception:
        raise

@app.route('/')
def index():
    return (
        "Event-Driven News Sentiment Micro-API\n\n"
        "POST /sentiment with JSON {\"ticker\":..., \"text\":...} or {\"url\":...}"
    )

@app.route('/sentiment', methods=['POST'])
def sentiment():
    try:
        data = request.get_json(force=True)
    except Exception:
        return jsonify({"error": "invalid or missing JSON body"}), 400

    if not isinstance(data, dict):
        return jsonify({"error": "JSON body must be an object"}), 400

    ticker = data.get('ticker')
    text = data.get('text')
    url = data.get('url')

    if not text and not url:
        return jsonify({"error": "provide 'text' or 'url' in JSON payload"}), 400

    fetched_from = None
    if url and not text:
        try:
            text = fetch_text_from_url(url)
            fetched_from = url
        except Exception as e:
            return jsonify({"error": f"failed to fetch url: {e}"}), 400

    if not text or not text.strip():
        return jsonify({"error": "no text to analyze"}), 400

    sentiment_score, explanation = score_text(text)

    # trading action thresholds
    if sentiment_score > 0.3:
        action = 'buy'
    elif sentiment_score < -0.3:
        action = 'sell'
    else:
        action = 'hold'

    resp = {
        "sentiment": sentiment_score,
        "action": action,
        "explanation": explanation
    }
    if ticker:
        resp['ticker'] = ticker
    if fetched_from:
        resp['fetched_from'] = fetched_from

    return jsonify(resp)


def demo_run():
    """Run a quick terminal demo and exit. This makes main.py safe for smoke tests.
    To run the server instead, start with the 'serve' argument:
      python main.py serve
    """
    sample = {
        "ticker": "tsla.us",
        "text": "Company reports stronger-than-expected deliveries and beats expectations"
    }
    print("Sentiment Micro-API demo (no server started):")
    print("Sample input:")
    print(json.dumps(sample, indent=2))
    sentiment_score, explanation = score_text(sample['text'])
    if sentiment_score > 0.3:
        action = 'buy'
    elif sentiment_score < -0.3:
        action = 'sell'
    else:
        action = 'hold'
    resp = {
        "ticker": sample['ticker'],
        "sentiment": sentiment_score,
        "action": action,
        "explanation": explanation
    }
    print("\nResult:")
    print(json.dumps(resp, indent=2))
    print("\nTo run the API server: python main.py serve")
    print("Then POST JSON to http://127.0.0.1:5000/sentiment as described in the README.")


def main():
    # If the user asked to serve, run the Flask app. Otherwise run a short demo and exit.
    if len(sys.argv) > 1 and sys.argv[1] in ("serve", "--serve", "runserver"):
        print("Starting Sentiment Micro-API on http://127.0.0.1:5000")
        print("POST JSON to /sentiment with {'ticker':..., 'text':...} or {'url':...}")
        app.run(host='127.0.0.1', port=5000)
    else:
        demo_run()

if __name__ == '__main__':
    main()
