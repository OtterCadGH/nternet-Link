#!/usr/bin/env python3
"""
nspire-ai-proxy: Local proxy server for TI-Nspire AI Camera Solver.
Receives requests from ESP32 over WiFi, forwards to Groq API.
"""

import os
import sys
import logging
from flask import Flask, request, jsonify
from openai import OpenAI

app = Flask(__name__)
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
log = logging.getLogger("nspire-proxy")

client = OpenAI(
    api_key=os.environ.get("GROQ_API_KEY", ""),
    base_url="https://api.groq.com/openai/v1",
)

VISION_MODEL = os.environ.get("VISION_MODEL", "meta-llama/llama-4-maverick-17b-128e-instruct")
TEXT_MODEL = os.environ.get("TEXT_MODEL", "llama-3.3-70b-versatile")

SYSTEM_PROMPT = (
    "You are a math/data science tutor for a TI-Nspire calculator. FORMAT RULES: "
    "1) PLAIN TEXT only - no LaTeX, markdown, or special symbols. "
    "2) MATRICES: Align columns with spaces so entries line up vertically. Each row on its own line. "
    "3) FRACTIONS: a/b format (1/2, -3/4, 11/12). "
    "4) POWERS: x^2, e^x. ROOTS: sqrt(x), cbrt(x). "
    "5) GREEK: spell out (alpha, beta, sigma, mu, theta, pi, lambda). "
    "6) STATS: x-bar=mean, s=std dev, P(X)=probability, E[X]=expected value, Var(X)=variance. "
    "7) CALCULUS: d/dx, integral(f dx), lim(x->a), sum(i=1 to n). "
    "8) VECTORS: <a,b,c> or [a,b,c]. SETS: {1,2,3}, union, intersect. "
    "9) LINEAR ALGEBRA: det(A), A^T=transpose, A^(-1)=inverse, rank(A), null(A). "
    "Number your steps. Be concise - small screen display."
)

VISION_PROMPT = (
    "Read this image and solve the math problem. Output in PLAIN TEXT only. "
    "No LaTeX, no markdown. Use x^2 for powers, sqrt() for roots, a/b for fractions. "
    "Show steps. Be concise."
)


@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok", "vision_model": VISION_MODEL, "text_model": TEXT_MODEL})


@app.route("/vision", methods=["POST"])
def vision():
    data = request.get_json()
    if not data or "image" not in data:
        return jsonify({"error": "Missing 'image' field"}), 400

    base64_image = data["image"]
    log.info(f"Vision request: {len(base64_image)} chars base64")

    try:
        response = client.chat.completions.create(
            model=VISION_MODEL,
            max_tokens=4096,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/jpeg;base64,{base64_image}"
                            },
                        },
                        {"type": "text", "text": VISION_PROMPT},
                    ],
                }
            ],
        )

        result = response.choices[0].message.content
        log.info(f"Vision response: {len(result)} chars")
        return jsonify({"result": result})

    except Exception as e:
        log.error(f"Vision error: {e}")
        return jsonify({"error": str(e)}), 500


@app.route("/ask", methods=["POST"])
def ask():
    data = request.get_json()
    if not data or "question" not in data:
        return jsonify({"error": "Missing 'question' field"}), 400

    question = data["question"]
    history = data.get("history", [])
    log.info(f"Ask request: '{question[:50]}...' with {len(history)} history msgs")

    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    for msg in history:
        messages.append({"role": msg["role"], "content": msg["content"]})
    messages.append({"role": "user", "content": question})

    try:
        response = client.chat.completions.create(
            model=TEXT_MODEL,
            max_tokens=4096,
            messages=messages,
        )

        result = response.choices[0].message.content
        log.info(f"Ask response: {len(result)} chars")
        return jsonify({"result": result})

    except Exception as e:
        log.error(f"Ask error: {e}")
        return jsonify({"error": str(e)}), 500


def main():
    port = int(os.environ.get("PROXY_PORT", 8080))

    if not os.environ.get("GROQ_API_KEY"):
        print("ERROR: GROQ_API_KEY environment variable not set.")
        print("Get your free key at: https://console.groq.com/keys")
        sys.exit(1)

    log.info(f"Starting nspire-ai-proxy on port {port}")
    log.info(f"Vision model: {VISION_MODEL}")
    log.info(f"Text model: {TEXT_MODEL}")
    log.info(f"Health check: http://localhost:{port}/health")

    # Bind to 0.0.0.0 so ESP32 can reach us over WiFi
    app.run(host="0.0.0.0", port=port)


if __name__ == "__main__":
    main()
