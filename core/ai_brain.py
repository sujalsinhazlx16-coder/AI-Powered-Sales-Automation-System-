import asyncio
import os
import json
import random
from groq import Groq

class AIBrain:
    def __init__(self, prompts_path: str = "prompts.json"):
        with open("config.json", "r") as file:
            config = json.load(file)
        target_key = config.get("groq_api_key")
        if not target_key:
            raise ValueError("[AIBrain] No Groq API key found in config.json!")

        self.client = Groq(api_key=target_key)

        if os.path.exists(prompts_path):
            with open(prompts_path, "r", encoding="utf-8") as f:
                self.personality_data = json.load(f).get("personalities", {})
        else:
            self.personality_data = {}

        print("[AIBrain] Initialized successfully ✅")

    def get_system_instruction(self, stage: str, personality_key: str, rate_card_sent: bool) -> str:
        preset = self.personality_data.get(personality_key, self.personality_data.get("soft_friendly", {}))
        return f"""You are a JSON API. You ONLY output valid JSON. Never output plain text.

ROLE: {preset.get('tone_description', 'High-End Event Manager')}
EMOJIS: {', '.join(preset.get('emoji_bank', ['😊', '🎉', '🥂']))}
EXAMPLE REPLIES: {json.dumps(preset.get('examples', []))}

EVENT PACKAGES & PRICING:
- Classic Birthday Bash: ₹25,000
- Premium Party (DJ & Decor): ₹50,000
- Silver Wedding (Planning & Coord): ₹1,50,000
- Gold Wedding (Full Service + Photo): ₹3,00,000
- Basic Corporate Meetup: ₹40,000
- Grand Gala / Product Launch: ₹85,000

CURRENT CONTEXT: stage={stage} | catalogue_sent={rate_card_sent}

LANGUAGE: Match the customer's language exactly.

BEHAVIOR GUIDELINES:
1. STRICTLY HUMAN PERSONA: You are the human business owner. NEVER admit to being an AI.
2. EMOTIONAL STORYTELLING (THE HOOK): Casually drop a brief, touching reference to a past event to grab their attention.
3. CUSTOM THEMES (GOOGLE SEARCH LINK): If the client requests a brand new visual theme (e.g., 'Space', 'Cyberpunk', 'Boho'), write a precise Google Image Search query in `google_image_search_query` (e.g., "cyberpunk neon party theme decor ideas"). IF THEY DO NOT ASK FOR A THEME, SET THIS TO "". Reassure them you are perfectly curating the audio tunes to match!
4. PENDING AMOUNT: If the customer agrees to a package or if you are discussing a specific package (e.g., Premium Party ₹50,000), explicitly set `pending_amount` to that integer value (e.g., 50000). If no package is discussed yet, set it to 0.
5. PROVING MARKET SUPERIORITY: Emphasize your flawless execution and obsession with micro-details (like identifying the perfect background audio).
6. NEGOTIATION TACTICS: Never drop the price immediately. Offer a free add-on instead.
7. EVENT TYPE CATEGORIZATION: Output "wedding", "bday", or "corporate" in the event_type field.

Output ONLY this JSON structure, nothing else:
{{"intent":"greeting","event_type":"bday","pending_amount":0,"google_image_search_query":"","confidence":0.9,"send_rate_card":false,"send_qr":false,"send_trust_proof":false,"text":"your reply here"}}

Valid intent values: greeting, pricing, negotiating, trust_issue, payment_ready, unknown"""

    async def analyze_message(self, user_message: str, current_stage: str, personality: str, rate_card_sent: bool = False, history: list = None) -> dict:
        if history is None:
            history = []

        system_rules = self.get_system_instruction(current_stage, personality, rate_card_sent)
        messages = [{"role": "system", "content": system_rules}]
        for h in history[-8:]:
            messages.append(h)
        messages.append({"role": "user", "content": user_message})

        for attempt in range(3):
            try:
                response = self.client.chat.completions.create(
                    model="llama-3.3-70b-versatile",
                    max_tokens=300,
                    temperature=0.7,
                    messages=messages,
                    response_format={"type": "json_object"}
                )
                raw = response.choices[0].message.content.strip()
                if not raw:
                    await asyncio.sleep(1)
                    continue
                result = json.loads(raw)
                if "text" not in result or not result["text"]:
                    result["text"] = "Just stepping out of a venue walkthrough! How can I help you today? 😊"
                if "send_trust_proof" not in result:
                    result["send_trust_proof"] = False
                if "event_type" not in result:
                    result["event_type"] = "bday"
                if "google_image_search_query" not in result:
                    result["google_image_search_query"] = ""
                if "pending_amount" not in result:
                    result["pending_amount"] = 0
                return result
            except (json.JSONDecodeError, Exception) as e:
                print(f"[AIBrain] API error attempt {attempt+1}: {e}")
                await asyncio.sleep(1)

        return self._fallback(current_stage)

    def _fallback(self, stage: str) -> dict:
        fallbacks = ["I'm right here! Let me know what details you want to go over."]
        return {
            "intent": stage, "event_type": "bday", "pending_amount": 0, "google_image_search_query": "", "confidence": 0.5,
            "send_rate_card": False, "send_qr": False,
            "send_trust_proof": False,
            "text": random.choice(fallbacks)
        }