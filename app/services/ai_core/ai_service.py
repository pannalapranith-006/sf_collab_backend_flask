import requests
import re
import logging
from time import time
from datetime import datetime
from flask import current_app
from flask_jwt_extended import get_jwt_identity

from .injection import detect_prompt_injection
from .output_filter import detect_sensitive_output
from .system_prompts import get_system_prompt
from .response_builder import build_refusal


# ==============================
# GLOBAL LIMIT CONFIG
# ==============================

MAX_PROMPT_LENGTH = 6000
MAX_OUTPUT_LENGTH = 20000
MAX_TOKENS_PER_REQUEST = 1500

MAX_REQUESTS_PER_MINUTE = 30
MAX_REQUESTS_PER_DAY = 500


# ==============================
# IN-MEMORY TRACKING
# ==============================

USER_RATE_LIMIT = {}
USER_DAILY_USAGE = {}


class AIService:

    # ==============================
    # RATE LIMIT CHECK
    # ==============================

    @staticmethod
    def check_rate_limit(user_id):

        now = time()

        window = USER_RATE_LIMIT.get(user_id, [])

        # keep only last 60 seconds
        window = [t for t in window if now - t < 60]

        if len(window) >= MAX_REQUESTS_PER_MINUTE:
            raise ValueError("AI rate limit exceeded. Please wait before sending more requests.")

        window.append(now)
        USER_RATE_LIMIT[user_id] = window

    # ==============================
    # DAILY USAGE LIMIT
    # ==============================

    @staticmethod
    def check_daily_limit(user_id):

        today = datetime.utcnow().date()

        usage = USER_DAILY_USAGE.get(user_id)

        if not usage:
            USER_DAILY_USAGE[user_id] = {
                "date": today,
                "count": 1
            }
            return

        # reset daily
        if usage["date"] != today:
            USER_DAILY_USAGE[user_id] = {
                "date": today,
                "count": 1
            }
            return

        if usage["count"] >= MAX_REQUESTS_PER_DAY:
            raise ValueError("Daily AI usage limit reached")

        usage["count"] += 1

    # ==============================
    # INPUT GUARDRAILS
    # ==============================

    @staticmethod
    def preprocess_input(feature: str, user_input: str):

        if detect_prompt_injection(user_input):
            return build_refusal("Prompt injection attempt detected.")

        return None

    # ==============================
    # OUTPUT GUARDRAILS
    # ==============================

    @staticmethod
    def postprocess_output(response_text: str):

        if detect_sensitive_output(response_text):
            return build_refusal("Sensitive or unsafe output blocked.")

        return None

    # ==============================
    # REMOVE CHAIN OF THOUGHT
    # ==============================

    @staticmethod
    def remove_thinking(text: str):

        if not text:
            return text

        text = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL)

        return text.strip()

    # ==============================
    # BUILD MESSAGES
    # ==============================

    @staticmethod
    def build_messages(feature: str, user_input: str, context: str = None):

        system_prompt = get_system_prompt(feature)

        messages = [
            {"role": "system", "content": system_prompt}
        ]

        if context:
            messages.append({
                "role": "system",
                "content": f"Context:\n{context}"
            })

        messages.append({
            "role": "user",
            "content": user_input
        })

        return messages

    # ==============================
    # CALL HF PROXY MODEL
    # ==============================

    @staticmethod
    def call_model(messages, temperature=0.7, max_tokens=2048):

        HF_URL = current_app.config.get("HF_PROXY_URL")
        HF_API_KEY = current_app.config.get("HF_PROXY_KEY")

        if not HF_URL or not HF_API_KEY:
            raise RuntimeError("HF proxy configuration missing")

        max_tokens = min(max_tokens, MAX_TOKENS_PER_REQUEST)

        headers = {
            "Authorization": f"Bearer {HF_API_KEY}",
            "Content-Type": "application/json"
        }

        payload = {
            "model": "advisor-model",
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens
        }

        response = requests.post(
            f"{HF_URL}/v1/chat/completions",
            headers=headers,
            json=payload,
            timeout=45
        )

        if response.status_code != 200:
            raise Exception(f"HF Proxy Error: {response.text}")

        data = response.json()

        return data["choices"][0]["message"]["content"]

    # ==============================
    # MAIN GENERATION ENTRYPOINT
    # ==============================

    @staticmethod
    def generate(feature: str, user_input: str, context: str = None,
                 temperature=0.7, max_tokens=2048):

        # ------------------------------
        # PROMPT SIZE PROTECTION
        # ------------------------------

        if len(user_input) > MAX_PROMPT_LENGTH:
            raise ValueError("Prompt too large")

        # ------------------------------
        # USER RATE LIMIT
        # ------------------------------

        try:
            user_id = get_jwt_identity()
        except Exception:
            user_id = "anonymous"

        AIService.check_rate_limit(user_id)
        AIService.check_daily_limit(user_id)

        # ------------------------------
        # INPUT GUARDRAILS
        # ------------------------------

        guardrail_check = AIService.preprocess_input(feature, user_input)

        if guardrail_check:
            return guardrail_check

        # ------------------------------
        # BUILD PROMPT
        # ------------------------------

        messages = AIService.build_messages(feature, user_input, context)

        # ------------------------------
        # MODEL CALL
        # ------------------------------

        response_text = AIService.call_model(
            messages,
            temperature=temperature,
            max_tokens=max_tokens
        )

        # ------------------------------
        # REMOVE THINKING
        # ------------------------------

        response_text = AIService.remove_thinking(response_text)

        # ------------------------------
        # OUTPUT GUARDRAILS
        # ------------------------------

        post_guardrail = AIService.postprocess_output(response_text)

        if post_guardrail:
            return post_guardrail

        # ------------------------------
        # RESPONSE SIZE PROTECTION
        # ------------------------------

        if len(response_text) > MAX_OUTPUT_LENGTH:
            response_text = response_text[:MAX_OUTPUT_LENGTH]

        # ------------------------------
        # LOGGING
        # ------------------------------

        logging.info({
            "event": "ai_request",
            "feature": feature,
            "user_id": user_id,
            "prompt_size": len(user_input),
            "timestamp": datetime.utcnow().isoformat()
        })

        return {
            "response": response_text,
            "guardrail_triggered": False
        }
