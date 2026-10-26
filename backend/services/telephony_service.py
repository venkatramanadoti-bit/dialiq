import os
import asyncio
import base64
import json
from typing import Dict, Any, Optional, List
from datetime import datetime
from dotenv import load_dotenv
from twilio.rest import Client
from twilio.twiml.voice_response import VoiceResponse, Gather, Say, Dial
import httpx

load_dotenv()

TELEPHONY_ACCOUNT_SID = os.getenv("TELEPHONY_ACCOUNT_SID")
TELEPHONY_AUTH_TOKEN = os.getenv("TELEPHONY_AUTH_TOKEN")
TELEPHONY_PHONE_NUMBER = os.getenv("TELEPHONY_PHONE_NUMBER")
DEMO_MODE = os.getenv("DEMO_MODE", "false").lower() == "true"
PER_MINUTE_RATE = float(os.getenv("PER_MINUTE_RATE", "6.0"))

class TelephonyService:
    def __init__(self):
        self.demo_mode = DEMO_MODE
        self.account_sid = TELEPHONY_ACCOUNT_SID
        self.auth_token = TELEPHONY_AUTH_TOKEN
        self.phone_number = TELEPHONY_PHONE_NUMBER
        self.client = None
        self.active_calls = {}

        if not self.demo_mode and self.account_sid and self.account_sid != "YOUR_TELEPHONY_SID_HERE":
            self.client = Client(self.account_sid, self.auth_token)

    async def initiate_call(
        self,
        to_number: str,
        agent_config: Dict[str, Any],
        webhook_base_url: str
    ) -> Dict[str, Any]:
        """Initiate an outbound call via Twilio"""
        if self.demo_mode:
            return await self._demo_initiate_call(to_number, agent_config)

        if not self.client:
            raise ValueError("Twilio client not configured")

        try:
            # Create TwiML for the call
            twiml_url = f"{webhook_base_url}/api/telephony/voice-webhook"

            call = self.client.calls.create(
                to=to_number,
                from_=self.phone_number,
                url=twiml_url,
                method="POST",
                status_callback=f"{webhook_base_url}/api/telephony/status-webhook",
                status_callback_method="POST",
                status_callback_event=["initiated", "ringing", "answered", "completed"],
                record=True,
                recording_channels="dual",
                recording_status_callback=f"{webhook_base_url}/api/telephony/recording-webhook",
                machine_detection="Enable",
                timeout=30
            )

            return {
                "call_sid": call.sid,
                "status": call.status,
                "to": to_number,
                "from": self.phone_number
            }
        except Exception as e:
            raise Exception(f"Failed to initiate call: {str(e)}")

    async def _demo_initiate_call(
        self,
        to_number: str,
        agent_config: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Demo mode call initiation"""
        import random
        call_sid = f"demo_call_{datetime.now().timestamp()}"

        # Simulate call states
        await asyncio.sleep(0.5)
        await asyncio.sleep(1.0)

        outcomes = ["answered", "busy", "no_answer", "voicemail"]
        weights = [0.6, 0.15, 0.15, 0.1]
        outcome = random.choices(outcomes, weights=weights)[0]

        if outcome == "answered":
            duration = random.randint(30, 300)
            await asyncio.sleep(min(duration / 10, 3))

            return {
                "call_sid": call_sid,
                "status": "completed",
                "outcome": "answered",
                "duration": duration,
                "cost": round(duration / 60 * PER_MINUTE_RATE, 2),
                "recording_url": f"/demo/recordings/{call_sid}.wav"
            }
        elif outcome == "busy":
            return {
                "call_sid": call_sid,
                "status": "completed",
                "outcome": "busy",
                "duration": 0,
                "cost": 0,
                "recording_url": None
            }
        elif outcome == "voicemail":
            return {
                "call_sid": call_sid,
                "status": "completed",
                "outcome": "voicemail",
                "duration": 15,
                "cost": round(15 / 60 * PER_MINUTE_RATE, 2),
                "recording_url": f"/demo/recordings/{call_sid}_vm.wav"
            }
        else:
            return {
                "call_sid": call_sid,
                "status": "completed",
                "outcome": "no_answer",
                "duration": 0,
                "cost": 0,
                "recording_url": None
            }

    def generate_twiml(self, agent_config: Dict[str, Any], action_url: str, webhook_base_url: str) -> str:
        """Generate TwiML for call handling"""
        response = VoiceResponse()

        # Initial greeting
        greeting = agent_config.get("greeting_message", "Hello! This is an AI assistant from DialIQ.")
        language = agent_config.get("language", "en-IN")

        # Map language to Twilio voice language
        voice_language_map = {
            "en-IN": "en-IN",
            "hi-IN": "hi-IN",
            "te-IN": "te-IN",
            "ta-IN": "ta-IN",
            "hi-Latn-IN": "en-IN"  # Hinglish uses English voice
        }
        voice_lang = voice_language_map.get(language, "en-IN")

        response.say(greeting, voice="Polly.Aditi", language=voice_lang)

        # Gather speech input
        gather = Gather(
            input="speech",
            action=action_url,
            method="POST",
            speech_timeout="auto",
            language=voice_lang,
            enhanced=True,
            speech_model="phone_call"
        )
        gather.say("Please go ahead.", voice="Polly.Aditi", language=voice_lang)
        response.append(gather)

        # Fallback
        response.say("I didn't catch that. Let me transfer you to an agent.", voice="Polly.Aditi", language=voice_lang)

        # Transfer if enabled
        if agent_config.get("transfer_enabled") and agent_config.get("transfer_number"):
            dial = Dial()
            dial.number(agent_config["transfer_number"])
            response.append(dial)

        return str(response)

    def generate_continue_twiml(self, ai_response: str, action_url: str, language: str = "en-IN", transfer_number: str = None, transfer_enabled: bool = False) -> str:
        """Generate TwiML for continuing conversation"""
        response = VoiceResponse()

        voice_language_map = {
            "en-IN": "en-IN",
            "hi-IN": "hi-IN",
            "te-IN": "te-IN",
            "ta-IN": "ta-IN",
            "hi-Latn-IN": "en-IN"
        }
        voice_lang = voice_language_map.get(language, "en-IN")

        # AI response
        response.say(ai_response, voice="Polly.Aditi", language=voice_lang)

        # Gather next input
        gather = Gather(
            input="speech",
            action=action_url,
            method="POST",
            speech_timeout="auto",
            language=voice_lang,
            enhanced=True,
            speech_model="phone_call"
        )
        gather.say("Go ahead.", voice="Polly.Aditi", language=voice_lang)
        response.append(gather)

        # Fallback
        response.say("I didn't catch that. Let me transfer you to an agent.", voice="Polly.Aditi", language=voice_lang)

        if transfer_enabled and transfer_number:
            dial = Dial()
            dial.number(transfer_number)
            response.append(dial)

        return str(response)

    def generate_transfer_twiml(self, transfer_number: str) -> str:
        """Generate TwiML for transferring to human"""
        response = VoiceResponse()
        response.say("Transferring you to a human agent now. Please hold.", voice="Polly.Aditi", language="en-IN")
        dial = Dial()
        dial.number(transfer_number)
        response.append(dial)
        return str(response)

    def generate_end_call_twiml(self, closing_message: str = "Thank you for your time. Goodbye!") -> str:
        """Generate TwiML to end call"""
        response = VoiceResponse()
        response.say(closing_message, voice="Polly.Aditi", language="en-IN")
        response.hangup()
        return str(response)

    async def process_speech_webhook(
        self,
        call_sid: str,
        speech_result: str,
        confidence: float,
        agent_config: Dict[str, Any],
        conversation_history: List[Dict[str, Any]],
        webhook_base_url: str
    ) -> Dict[str, Any]:
        """Process speech from Twilio webhook and generate response"""
        from services.ai_service import ai_service

        # Add user speech to history
        conversation_history.append({
            "speaker": "customer",
            "text": speech_result,
            "timestamp": datetime.now().timestamp(),
            "confidence": confidence
        })

        # Get AI response
        result = await ai_service.generate_response(agent_config, conversation_history, speech_result)

        # Add AI response to history
        conversation_history.append({
            "speaker": "ai",
            "text": result["text"],
            "timestamp": datetime.now().timestamp()
        })

        # Generate TTS audio for the response
        tts_audio = await ai_service.text_to_speech(
            result["text"],
            language=agent_config.get("language", "en-IN")
        )

        return {
            "response_text": result["text"],
            "sentiment_score": result["sentiment_score"],
            "disposition": result["disposition"],
            "should_transfer": result["should_transfer"],
            "conversation_history": conversation_history,
            "tts_audio_base64": base64.b64encode(tts_audio).decode() if tts_audio else None,
            "twiml": self.generate_continue_twiml(
                result["text"],
                f"{webhook_base_url}/api/telephony/speech-webhook",
                agent_config.get("language", "en-IN"),
                agent_config.get("transfer_number"),
                agent_config.get("transfer_enabled", False)
            ) if not result["should_transfer"] else self.generate_transfer_twiml(agent_config.get("transfer_number"))
        }

    def calculate_cost(self, duration_seconds: int) -> float:
        """Calculate call cost based on duration"""
        minutes = max(1, (duration_seconds + 59) // 60)
        return round(minutes * PER_MINUTE_RATE, 2)

    def get_call_details(self, call_sid: str) -> Optional[Dict[str, Any]]:
        """Get call details from Twilio"""
        if self.demo_mode:
            return None

        if not self.client:
            return None

        try:
            call = self.client.calls(call_sid).fetch()
            return {
                "sid": call.sid,
                "status": call.status,
                "duration": call.duration,
                "start_time": call.start_time,
                "end_time": call.end_time,
                "price": call.price,
                "direction": call.direction,
                "to": call.to,
                "from": call.from_
            }
        except Exception as e:
            print(f"Error fetching call details: {e}")
            return None

    def get_recording_url(self, call_sid: str) -> Optional[str]:
        """Get recording URL for a call"""
        if self.demo_mode:
            return None

        if not self.client:
            return None

        try:
            recordings = self.client.recordings.list(call_sid=call_sid, limit=1)
            if recordings:
                recording = recordings[0]
                return f"https://api.twilio.com{recording.uri.replace('.json', '.mp3')}"
        except Exception as e:
            print(f"Error fetching recording: {e}")
        return None

# Global instance
telephony_service = TelephonyService()