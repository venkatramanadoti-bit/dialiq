import os
import json
import asyncio
import base64
from typing import List, Dict, Any, Optional
from datetime import datetime
import google.generativeai as genai
import httpx
from dotenv import load_dotenv

load_dotenv()

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
STT_API_KEY = os.getenv("STT_API_KEY")
TTS_API_KEY = os.getenv("TTS_API_KEY")
DEMO_MODE = os.getenv("DEMO_MODE", "false").lower() == "true"

# Configure Gemini
if GEMINI_API_KEY and GEMINI_API_KEY != "YOUR_GEMINI_API_KEY_HERE":
    genai.configure(api_key=GEMINI_API_KEY)
    GEMINI_MODEL = genai.GenerativeModel('gemini-1.5-flash')
else:
    GEMINI_MODEL = None

# STT/TTS endpoints (using the same key for both as per your config)
STT_API_URL = "https://api.sarvam.ai/speech-to-text"
TTS_API_URL = "https://api.sarvam.ai/text-to-speech"

class AIService:
    def __init__(self):
        self.demo_mode = DEMO_MODE
        self.demo_responses = self._load_demo_responses()

    def _load_demo_responses(self) -> Dict[str, List[str]]:
        return {
            "greeting": [
                "Hello! This is {agent_name} from {company}. How are you doing today?",
                "Hi there! I'm {agent_name} calling from {company}. Do you have a moment to chat?",
                "Good {time_of_day}! This is {agent_name} from {company}. I hope I'm not catching you at a bad time."
            ],
            "objection_price": [
                "I completely understand your concern about pricing. Many of our clients felt the same way initially, but they found that the ROI more than justifies the investment. Would you like me to share a quick case study?",
                "That's a fair point. Our pricing is actually very competitive when you consider the cost per qualified lead. Most clients see a 3-5x return within the first month. Can I walk you through the numbers?",
                "I appreciate you bringing that up. We offer flexible plans starting at just Rs. 5000/month with no long-term contracts. Would a custom quote based on your expected call volume help?"
            ],
            "objection_not_interested": [
                "I totally respect that. May I ask what solution you're currently using for your outbound calling needs?",
                "Fair enough! Just curious - are you handling calls manually right now, or using another platform?",
                "No problem at all. If things change in the future, we'd love to show you how we've helped similar companies increase conversions by 40%."
            ],
            "objection_busy": [
                "I completely understand - you sound busy. When would be a better time for a quick 2-minute chat?",
                "No worries at all! I can call back at a more convenient time. What works for you - later today or tomorrow?",
                "I appreciate your time. Let me know when you're free and I'll reach out then."
            ],
            "interest_high": [
                "That's great to hear! Let me connect you with our specialist who can walk you through a personalized demo. What's the best number to reach you?",
                "Excellent! I'd love to set up a demo tailored to your use case. Can I have your email to send over some details and schedule a time?",
                "Perfect! Our team can get you set up with a free trial this week. Shall I have someone call you back with the details?"
            ],
            "callback_request": [
                "Absolutely, I can schedule a callback. What day and time works best for you?",
                "Sure thing! I'll make a note to call you back. Any specific time window you prefer?",
                "Of course. Let me get your preferred callback time and we'll reach out then."
            ],
            "voicemail": [
                "Hi, this is {agent_name} from {company}. I wanted to share how we're helping businesses like yours automate their outbound calling with AI. Give me a call back at {callback_number} or visit our website. Thanks!",
                "Hello, this is {agent_name} calling from {company}. We have an AI solution that can handle thousands of calls simultaneously with human-like conversations. Interested in a demo? Call us back at {callback_number}."
            ],
            "closing": [
                "Thank you for your time today! Have a wonderful {time_of_day}!",
                "It was great speaking with you. Looking forward to helping you scale your outreach. Goodbye!",
                "Thanks for chatting! I'll send over the information we discussed. Have a great day!"
            ]
        }

    def _get_time_of_day(self) -> str:
        hour = datetime.now().hour
        if hour < 12:
            return "morning"
        elif hour < 17:
            return "afternoon"
        else:
            return "evening"

    async def generate_response(
        self,
        agent_config: Dict[str, Any],
        conversation_history: List[Dict[str, Any]],
        user_input: str
    ) -> Dict[str, Any]:
        """Generate AI response based on agent config and conversation history"""

        if self.demo_mode or GEMINI_MODEL is None:
            return await self._demo_generate_response(agent_config, conversation_history, user_input)

        # Production mode with Gemini
        system_prompt = self._build_system_prompt(agent_config)
        messages = [{"role": "system", "content": system_prompt}]

        for entry in conversation_history:
            role = "assistant" if entry["speaker"] == "ai" else "user"
            messages.append({"role": role, "content": entry["text"]})

        messages.append({"role": "user", "content": user_input})

        try:
            # Convert to Gemini format
            gemini_messages = []
            for msg in messages:
                if msg["role"] == "system":
                    gemini_messages.append({"role": "user", "parts": [msg["content"]]})
                    gemini_messages.append({"role": "model", "parts": ["Understood. I'll follow these guidelines."]})
                elif msg["role"] == "user":
                    gemini_messages.append({"role": "user", "parts": [msg["content"]]})
                else:
                    gemini_messages.append({"role": "model", "parts": [msg["content"]]})

            response = await GEMINI_MODEL.generate_content_async(gemini_messages)
            ai_text = response.text

            # Analyze sentiment and determine disposition
            sentiment = await self._analyze_sentiment(user_input, ai_text)
            disposition = self._determine_disposition(conversation_history, user_input, ai_text)

            return {
                "text": ai_text,
                "sentiment_score": sentiment,
                "disposition": disposition,
                "should_transfer": self._should_transfer(agent_config, user_input, disposition)
            }
        except Exception as e:
            print(f"Gemini API error: {e}")
            return await self._demo_generate_response(agent_config, conversation_history, user_input)

    def _build_system_prompt(self, agent_config: Dict[str, Any]) -> str:
        prompt = agent_config.get("system_prompt", "")
        prompt += f"\n\nYou are {agent_config.get('name', 'an AI assistant')} from {agent_config.get('company', 'our company')}."
        prompt += f"\nLanguage: {agent_config.get('language', 'English (India)')}"
        prompt += f"\nGreeting: {agent_config.get('greeting_message', '')}"

        if agent_config.get("knowledge_base"):
            prompt += "\n\nKnowledge Base (answer ONLY from this information):"
            for kb in agent_config["knowledge_base"]:
                prompt += f"\nQ: {kb['question']}\nA: {kb['answer']}"

        if agent_config.get("objection_handling"):
            prompt += "\n\nObjection Handling Rules:"
            for obj in agent_config["objection_handling"]:
                prompt += f"\nIf customer says: '{obj['trigger']}' -> Respond: '{obj['response']}'"

        prompt += "\n\nGuidelines: Be conversational, empathetic, and professional. Keep responses concise (1-2 sentences). Don't mention you're an AI unless asked. Speak naturally in the selected language."
        return prompt

    async def _demo_generate_response(
        self,
        agent_config: Dict[str, Any],
        conversation_history: List[Dict[str, Any]],
        user_input: str
    ) -> Dict[str, Any]:
        """Demo mode response generation"""
        await asyncio.sleep(0.5)  # Simulate processing delay

        user_lower = user_input.lower()
        agent_name = agent_config.get("name", "DialIQ Agent")
        company = agent_config.get("company", "DialIQ")
        time_of_day = self._get_time_of_day()
        callback_number = agent_config.get("transfer_number", "1800-XXX-XXXX")

        # Check for transfer triggers
        transfer_triggers = ["speak to human", "talk to manager", "real person", "human agent", "transfer me"]
        should_transfer = any(trigger in user_lower for trigger in transfer_triggers) and agent_config.get("transfer_enabled")

        if should_transfer:
            response_text = f"Absolutely, let me transfer you to a human agent right away. Please hold."
            disposition = "callback_requested"
            sentiment = 0.1
        elif not conversation_history or len(conversation_history) == 0:
            # First message - greeting
            template = random.choice(self.demo_responses["greeting"])
            response_text = template.format(agent_name=agent_name, company=company, time_of_day=time_of_day)
            disposition = None
            sentiment = 0.3
        elif any(word in user_lower for word in ["price", "cost", "expensive", "budget", "cheap", "afford", "rate"]):
            template = random.choice(self.demo_responses["objection_price"])
            response_text = template
            disposition = "follow_up"
            sentiment = 0.0
        elif any(word in user_lower for word in ["not interested", "don't need", "no thanks", "not looking", "happy with current"]):
            template = random.choice(self.demo_responses["objection_not_interested"])
            response_text = template
            disposition = "not_interested"
            sentiment = -0.3
        elif any(word in user_lower for word in ["busy", "in a meeting", "driving", "can't talk", "call back", "later"]):
            template = random.choice(self.demo_responses["objection_busy"])
            response_text = template
            disposition = "callback_requested"
            sentiment = 0.1
        elif any(word in user_lower for word in ["interested", "tell me more", "how does it work", "demo", "trial", "sign up", "pricing", "cost"]):
            template = random.choice(self.demo_responses["interest_high"])
            response_text = template
            disposition = "hot_lead"
            sentiment = 0.7
        elif any(word in user_lower for word in ["call back", "callback", "later", "another time", "schedule"]):
            template = random.choice(self.demo_responses["callback_request"])
            response_text = template
            disposition = "callback_requested"
            sentiment = 0.2
        elif len(conversation_history) > 6:
            # Closing after extended conversation
            template = random.choice(self.demo_responses["closing"])
            response_text = template.format(time_of_day=time_of_day)
            disposition = "follow_up"
            sentiment = 0.2
        else:
            # General response
            responses = [
                "That's interesting! Can you tell me more about your current process?",
                "I see. And how many calls does your team typically make per day?",
                "Got it. What's the biggest challenge you're facing with your current outreach?",
                "That makes sense. Would you be open to seeing a quick demo of how our AI handles objections?",
                "I understand. Many of our clients had similar setups before switching. What would make you consider a change?"
            ]
            import random
            response_text = random.choice(responses)
            disposition = "follow_up"
            sentiment = 0.1

        # Check knowledge base for specific answers
        if agent_config.get("knowledge_base"):
            for kb in agent_config["knowledge_base"]:
                if any(keyword in user_lower for keyword in kb["question"].lower().split()):
                    response_text = kb["answer"]
                    break

        return {
            "text": response_text,
            "sentiment_score": sentiment,
            "disposition": disposition,
            "should_transfer": should_transfer
        }

    async def _analyze_sentiment(self, user_input: str, ai_response: str) -> float:
        """Analyze sentiment of conversation"""
        if self.demo_mode or GEMINI_MODEL is None:
            # Simple keyword-based sentiment
            positive_words = ["interested", "great", "good", "yes", "sure", "love", "excellent", "perfect", "amazing"]
            negative_words = ["not interested", "no", "bad", "expensive", "waste", "useless", "hate", "terrible", "angry"]

            text = (user_input + " " + ai_response).lower()
            pos_count = sum(1 for w in positive_words if w in text)
            neg_count = sum(1 for w in negative_words if w in text)

            if pos_count + neg_count == 0:
                return 0.0
            return (pos_count - neg_count) / (pos_count + neg_count)

        # Production: Use Gemini for sentiment analysis
        try:
            prompt = f"Rate the sentiment of this conversation from -1 (very negative) to 1 (very positive):\nUser: {user_input}\nAI: {ai_response}\n\nReturn only a number."
            response = await GEMINI_MODEL.generate_content_async(prompt)
            return float(response.text.strip())
        except:
            return 0.0

    def _determine_disposition(
        self,
        conversation_history: List[Dict[str, Any]],
        user_input: str,
        ai_response: str
    ) -> Optional[str]:
        """Determine lead disposition based on conversation"""
        user_lower = user_input.lower()

        if any(word in user_lower for word in ["interested", "demo", "trial", "sign up", "pricing", "cost", "how much", "buy", "purchase"]):
            return "hot_lead"
        elif any(word in user_lower for word in ["call back", "callback", "later", "another time", "schedule", "email me"]):
            return "callback_requested"
        elif any(word in user_lower for word in ["not interested", "don't need", "no thanks", "happy with current", "remove me"]):
            return "not_interested"
        elif len(conversation_history) > 8:
            return "follow_up"
        return None

    def _should_transfer(
        self,
        agent_config: Dict[str, Any],
        user_input: str,
        disposition: Optional[str]
    ) -> bool:
        """Check if call should be transferred to human"""
        if not agent_config.get("transfer_enabled"):
            return False

        transfer_triggers = ["speak to human", "talk to manager", "real person", "human agent", "transfer me", "operator"]
        user_lower = user_input.lower()
        return any(trigger in user_lower for trigger in transfer_triggers)

    async def speech_to_text(self, audio_data: bytes, language: str = "en-IN") -> Dict[str, Any]:
        """Convert speech to text using STT API"""
        if self.demo_mode:
            return {"text": "", "confidence": 0.0, "error": "Demo mode - STT not available"}

        try:
            headers = {
                "api-subscription-key": STT_API_KEY,
                "Content-Type": "application/octet-stream"
            }
            params = {
                "language_code": language,
                "model": "saarika:v2"
            }

            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    STT_API_URL,
                    headers=headers,
                    params=params,
                    content=audio_data
                )

            if response.status_code == 200:
                result = response.json()
                return {
                    "text": result.get("transcript", ""),
                    "confidence": result.get("confidence", 0.0)
                }
            else:
                return {"text": "", "confidence": 0.0, "error": f"STT API error: {response.text}"}
        except Exception as e:
            return {"text": "", "confidence": 0.0, "error": str(e)}

    async def text_to_speech(self, text: str, language: str = "en-IN", speaker: str = "meera") -> bytes:
        """Convert text to speech using TTS API"""
        if self.demo_mode:
            # Return empty audio in demo mode
            return b""

        try:
            headers = {
                "api-subscription-key": TTS_API_KEY,
                "Content-Type": "application/json"
            }
            payload = {
                "inputs": [text],
                "target_language_code": language,
                "speaker": speaker,
                "pitch": 0,
                "pace": 1.0,
                "loudness": 1.0,
                "speech_sample_rate": 8000,
                "enable_preprocessing": True,
                "model": "bulbul:v1"
            }

            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    TTS_API_URL,
                    headers=headers,
                    json=payload
                )

            if response.status_code == 200:
                result = response.json()
                audio_base64 = result.get("audios", [None])[0]
                if audio_base64:
                    return base64.b64decode(audio_base64)
            return b""
        except Exception as e:
            print(f"TTS error: {e}")
            return b""

# Global instance
ai_service = AIService()