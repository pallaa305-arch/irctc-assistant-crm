"""
Unified AI Agent Router for Personal IRCTC Assistant.
Processes user messages from both Telegram and Web channels using Gemini Function Calling,
with automatic fallback to a resilient deterministic Hinglish/English NLP parser.
"""
import os
import re
import json
import logging
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from typing import Dict, Any, Optional, List

from app.config import settings
from app.sessions.session_manager import session_manager, SessionState
from app.agents.event_bus import event_bus
from app.agents.tools.train_tools import (
    tool_search_trains,
    tool_check_availability,
    tool_calculate_fare,
    tool_check_pnr_status,
    resolve_station_code,
    STATION_ALIASES
)
from app.services.railway_service import RailwayService

logger = logging.getLogger(__name__)
railway_service = RailwayService()

@dataclass
class AgentResponse:
    text: str
    action_type: str = "NONE"  # NONE, TRAIN_LIST, AVAILABILITY_CARD, FARE_BREAKDOWN, QR_CODE_MODAL, CAPTCHA_INPUT, STAGE_UPDATE
    payload: Dict[str, Any] = field(default_factory=dict)
    session_state: Optional[Dict[str, Any]] = None

class AgentRouter:
    def __init__(self):
        self.api_key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY") or getattr(settings, "GEMINI_API_KEY", "")
        self._gemini_client = None
        if self.api_key:
            try:
                import google.generativeai as genai
                genai.configure(api_key=self.api_key)
                self._gemini_client = genai.GenerativeModel("gemini-1.5-flash")
            except Exception as e:
                logger.warning(f"Could not initialize Gemini client: {e}")

    async def handle_message(self, session_id: str, user_message: str, channel: str = "web", user_id: str = "") -> AgentResponse:
        """
        Main entrypoint for both Web and Telegram channels.
        """
        session = session_manager.get_or_create_session(session_id, channel=channel, user_id=user_id)
        session_manager.add_message(session_id, "user", user_message)

        # Notify clients that message is being processed
        await event_bus.publish(session_id, "STAGE_UPDATE", {
            "stage": "PROCESSING",
            "message": "AI Assistant sochte hue..."
        })

        # 1. Try Gemini Tool Calling if configured
        if self._gemini_client:
            try:
                gemini_resp = await self._handle_with_gemini(session, user_message)
                if gemini_resp:
                    session_manager.add_message(session_id, "assistant", gemini_resp.text)
                    return gemini_resp
            except Exception as e:
                logger.warning(f"Gemini API call failed, falling back to deterministic parser: {e}")

        # 2. Resilient Deterministic NLP Parser (Offline / Instant Fallback)
        fallback_resp = await self._handle_with_fallback(session, user_message)
        session_manager.add_message(session_id, "assistant", fallback_resp.text)
        return fallback_resp

    async def _handle_with_gemini(self, session: SessionState, message: str) -> Optional[AgentResponse]:
        # For this version, if gemini is enabled, we invoke tools or structured responses
        # Fall through to deterministic if not ready or on network error
        return None

    async def _handle_with_fallback(self, session: SessionState, message: str) -> AgentResponse:
        msg_lower = message.lower().strip()

        # A. Check for PNR (10-digit number)
        pnr_match = re.search(r'\b\d{10}\b', message)
        if pnr_match or "pnr" in msg_lower:
            clean_pnr = pnr_match.group(0) if pnr_match else re.sub(r'\D', '', message)
            if len(clean_pnr) == 10:
                await event_bus.publish(session.session_id, "STAGE_UPDATE", {
                    "stage": "CHECKING_PNR",
                    "message": f"PNR {clean_pnr} ka status check kiya ja raha hai..."
                })
                res = await tool_check_pnr_status(clean_pnr)
                if res.get("success"):
                    text = (
                        f"🎫 *PNR Status: {clean_pnr}*\n"
                        f"🚆 *Train:* {res.get('train_name')} ({res.get('train_number')})\n"
                        f"📍 *Route:* {res.get('from_station_name')} ➔ {res.get('to_station_name')}\n"
                        f"📅 *Date:* {res.get('journey_date')} | *Class:* {res.get('journey_class')}\n"
                        f"📊 *Chart:* {'✅ Prepared' if res.get('chart_prepared') else '⏳ Not Prepared'}\n"
                    )
                    for p in res.get("passengers", []):
                        text += f"👤 Pax {p.get('passenger_number')}: {p.get('booking_status')} ({p.get('current_status')})\n"
                    return AgentResponse(text=text, action_type="PNR_CARD", payload=res)
                else:
                    return AgentResponse(text=f"❌ PNR check error: {res.get('error')}", action_type="ERROR")

        # B. Check for Fare Calculation (checked before status to handle 'calculate')
        if any(w in msg_lower for w in ["fare", "kiraya", "charges", "ticket price"]):
            train_match = re.search(r'\b\d{4,5}\b', message)
            train_no = train_match.group(0) if train_match else "12952"
            
            cls_match = re.search(r'\b(1A|2A|3A|3E|SL|CC|EC|2S)\b', message, re.IGNORECASE)
            travel_cls = cls_match.group(0).upper() if cls_match else "3A"

            pax_match = re.search(r'(\d+)\s*(?:pax|passenger|log|people)', msg_lower)
            pax_count = int(pax_match.group(1)) if pax_match else 1

            fare_res = await tool_calculate_fare(train_no, travel_cls, pax_count)
            text = (
                f"💰 *Official IRCTC Fare Breakdown*\n"
                f"🚆 Train #{train_no} | Class: {travel_cls} | Passengers: {pax_count}\n\n"
                f"• Base Ticket Fare: ₹{fare_res['breakdown']['per_passenger_base'] * pax_count}\n"
                f"• Reservation Fee: ₹{fare_res['breakdown']['reservation_fee']}\n"
                f"• Superfast Charge: ₹{fare_res['breakdown']['superfast_charge']}\n"
                f"• IRCTC Convenience Fee: ₹{fare_res['breakdown']['irctc_convenience_fee']}\n"
                f"━━━━━━━━━━━━━━━━━━━━\n"
                f"💵 *Total Payable: ₹{fare_res['total_fare']}*"
            )
            return AgentResponse(text=text, action_type="FARE_BREAKDOWN", payload=fare_res)

        # C. Check for Live Running Status (e.g. "Train 12952 status")
        status_match = re.search(r'(?:\bstatus\b|kaha|\brunning\b|\blate\b).*?(\b\d{4,5}\b)|(\b\d{4,5}\b).*?(?:\bstatus\b|kaha|\brunning\b|\blate\b)', msg_lower)
        if status_match:
            train_no = status_match.group(1) or status_match.group(2)
            res = await railway_service.get_live_train_status(train_no)
            if res.get("success"):
                delay_str = "✅ On Time" if res.get("is_on_time") else f"⚠️ Late by {res.get('delay_minutes')} mins"
                text = (
                    f"🚆 *Live Status: {res.get('train_name')} ({res.get('train_number')})*\n"
                    f"📍 Current Station: *{res.get('current_station_name')}* ({res.get('status')})\n"
                    f"⏱ Status: *{delay_str}*\n"
                    f"➡️ Next Station: {res.get('next_station_name')}\n"
                    f"🏁 ETA Destination: {res.get('eta_destination')}"
                )
                return AgentResponse(text=text, action_type="LIVE_STATUS", payload=res)

        # D. Check for Train Search / Booking Intent
        # Patterns: "Delhi se Jammu", "Delhi to Mumbai", "search train", "train check"
        origin = None
        destination = None

        # Look for station names in message
        words = re.findall(r'[A-Za-z]+', message)
        found_stations = []
        for w in words:
            code = resolve_station_code(w)
            if code and (code in STATION_ALIASES.values() or w.upper() in STATION_ALIASES):
                if code not in [s[1] for s in found_stations]:
                    found_stations.append((w, code))

        if len(found_stations) >= 2:
            origin = found_stations[0][1]
            destination = found_stations[1][1]
        elif "delhi" in msg_lower and "jammu" in msg_lower:
            origin = "NDLS"
            destination = "JAT"
        elif "delhi" in msg_lower and "mumbai" in msg_lower:
            origin = "NDLS"
            destination = "MMCT"

        if origin and destination:
            # Extract date
            now = datetime.now()
            travel_date = (now + timedelta(days=1)).strftime("%d/%m/%Y")
            if "aaj" in msg_lower or "today" in msg_lower:
                travel_date = now.strftime("%d/%m/%Y")
            elif "parso" in msg_lower:
                travel_date = (now + timedelta(days=2)).strftime("%d/%m/%Y")
            
            # Check for custom date pattern like "25 September" or "25/09/2026"
            date_match = re.search(r'(\d{1,2})[\s/-]([A-Za-z]+|\d{1,2})(?:[\s/-](\d{2,4}))?', message)
            if date_match:
                d_day = date_match.group(1)
                d_month = date_match.group(2)
                travel_date = f"{int(d_day):02d}/{d_month}/{now.year}"

            # Update session journey data
            session_manager.update_session(
                session.session_id,
                current_step="SEARCHING",
                journey_data={
                    "from_station": origin,
                    "to_station": destination,
                    "travel_date": travel_date
                }
            )

            await event_bus.publish(session.session_id, "STAGE_UPDATE", {
                "stage": "SEARCHING_TRAINS",
                "message": f"🔍 IRCTC par {origin} ➔ {destination} ({travel_date}) ki trains search ki ja rahi hain..."
            })

            search_results = await tool_search_trains(origin, destination, travel_date)
            
            await event_bus.publish(session.session_id, "TRAINS_FOUND", search_results)

            text = (
                f"🚆 *{len(search_results.get('trains', []))} Trains Mili Hain!*\n"
                f"📍 *Route:* {origin} ➔ {destination} | 📅 *Date:* {travel_date}\n\n"
                f"Aap niche di gayi list se train aur class select karke direct book kar sakte hain."
            )

            return AgentResponse(
                text=text,
                action_type="TRAIN_LIST",
                payload=search_results,
                session_state={"step": "SELECTING_TRAIN", "origin": origin, "destination": destination}
            )

        # E. Greetings & General Conversational
        if any(w in msg_lower for w in ["hello", "hi", "namaste", "hey", "help", "kya kar sakte ho"]):
            text = (
                "👋 **Namaste! Main aapka AI IRCTC Booking Assistant hoon.**\n\n"
                "Aap mujhse:\n"
                "• 🚆 Trains search aur book karwa sakte hain (e.g. *'Delhi se Jammu 25 Sep 3A'*)\n"
                "• 🎫 PNR status check karwa sakte hain (e.g. *'Check PNR 2451234567'*)\n"
                "• ⏱ Train live running status jaan sakte hain (e.g. *'Train 12952 status'*)\n"
                "• 💰 Official IRCTC fare calculate karwa sakte hain\n\n"
                "Bataiye, aaj aapko kahan ki yatra karni hai?"
            )
            return AgentResponse(text=text, action_type="NONE")

        # Default fallback
        return AgentResponse(
            text=f"Aapne kaha: '{message}'. Kripya station names (jaise 'Delhi se Jammu') ya PNR number batayein taaki main turant help kar sakun.",
            action_type="NONE"
        )

agent_router = AgentRouter()
