import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import uuid
import json
import logging
from datetime import datetime, date
from flask import Flask, request, jsonify, send_from_directory
import anthropic
from persona import get_persona
from retrieval import retrieve_context

app = Flask(__name__, static_folder='../static')
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

client = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY", ""))
MODEL = os.environ.get("MODEL", "claude-fable-5")

INVITE_CODE = os.environ.get("INVITE_CODE", "")
DAILY_LIMIT = int(os.environ.get("DAILY_LIMIT", 300))
PER_IP_LIMIT = int(os.environ.get("PER_IP_LIMIT", 30))

conversations: dict = {}
ratings: list = []
_usage: dict = {"global": 0, "by_ip": {}, "reset_date": str(date.today())}


def _reset_if_new_day():
    today = str(date.today())
    if _usage["reset_date"] != today:
        _usage["global"] = 0
        _usage["by_ip"] = {}
        _usage["reset_date"] = today


def _within_limits(ip: str) -> bool:
    _reset_if_new_day()
    return (
        _usage["global"] < DAILY_LIMIT
        and _usage["by_ip"].get(ip, 0) < PER_IP_LIMIT
    )


def _record(ip: str):
    _usage["global"] += 1
    _usage["by_ip"][ip] = _usage["by_ip"].get(ip, 0) + 1


@app.route("/")
def index():
    return send_from_directory(app.static_folder, "index.html")


@app.route("/chat", methods=["POST"])
def chat():
    data = request.get_json(silent=True) or {}

    if INVITE_CODE and data.get("invite_code") != INVITE_CODE:
        return jsonify({"error": "Unauthorized"}), 401

    ip = request.remote_addr
    if not _within_limits(ip):
        return jsonify({"error": "Bas, Parth. Kal milte hain — daily limit reached."}), 429

    message = (data.get("message") or "").strip()
    if not message:
        return jsonify({"error": "Empty message"}), 400

    mode = data.get("mode", "sarathi").lower()
    conv_id = data.get("conv_id") or str(uuid.uuid4())

    if conv_id not in conversations:
        conversations[conv_id] = []

    history = conversations[conv_id][-10:]
    context = retrieve_context(message)

    system_prompt = get_persona(mode)
    if context:
        system_prompt += (
            "\n\nRELEVANT WISDOM FROM THE DATABANK (use naturally if relevant, never force):\n"
            + context
        )

    messages = history + [{"role": "user", "content": message}]

    try:
        response = client.messages.create(
            model=MODEL,
            max_tokens=500,
            system=system_prompt,
            messages=messages,
        )

        reply = ""
        for block in response.content:
            if hasattr(block, "text"):
                reply = block.text
                break

        conversations[conv_id].append({"role": "user", "content": message})
        conversations[conv_id].append({"role": "assistant", "content": reply})
        if len(conversations[conv_id]) > 20:
            conversations[conv_id] = conversations[conv_id][-20:]

        _record(ip)
        logger.info(f"chat | mode={mode} | ip={ip}")

        return jsonify({"reply": reply, "conv_id": conv_id, "mode": mode})

    except Exception as e:
        logger.error(f"API error: {e}")
        return jsonify({"error": "Krishna is in samadhi. Try again in a moment."}), 500


@app.route("/rate", methods=["POST"])
def rate():
    data = request.get_json(silent=True) or {}
    entry = {
        "ts": datetime.now().isoformat(),
        "conv_id": data.get("conv_id"),
        "score": data.get("score"),
        "message": data.get("message"),
        "reply": data.get("reply"),
        "mode": data.get("mode"),
    }
    ratings.append(entry)
    try:
        with open("ratings.jsonl", "a") as f:
            f.write(json.dumps(entry) + "\n")
    except Exception:
        pass
    logger.info(f"RATING: {json.dumps(entry)}")
    return jsonify({"status": "ok", "message": "Jai Shri Krishna 🙏"})


@app.route("/health")
def health():
    return jsonify({"status": "ok", "model": MODEL})


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5001))
    app.run(debug=True, port=port)
