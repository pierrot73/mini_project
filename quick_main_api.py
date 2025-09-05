#!/usr/bin/env python3
"""
Iwacu Chatbot - API Principale (Version Démarrage Rapide)
"""
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, Response
from pydantic import BaseModel
from typing import Optional, List, Dict
import os
import csv
import json
import uuid
import re
from datetime import datetime, timedelta
from pathlib import Path

# Load environment if available
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

app = FastAPI(title="Iwacu Chatbot", version="1.0.0")

# Enable CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Models
class ChatMessage(BaseModel):
    text: str
    sender: Optional[str] = "web"

class ChatResponse(BaseModel):
    reply: str
    intent: str
    lang: str

class BookingRequest(BaseModel):
    date: str
    time: str
    party_size: int
    name: str
    phone: str
    area: Optional[str] = "int"
    notes: Optional[str] = ""

# Simple NLP
class SimpleNLP:
    def __init__(self):
        self.intent_patterns = {
            'menu': ['menu', 'carte', 'plat', 'manger', 'food', 'dish', 'eat'],
            'promos': ['promo', 'offre', 'réduction', 'discount', 'deal', 'happy hour'],
            'horaires': ['heure', 'horaire', 'ouvert', 'fermé', 'open', 'close', 'time'],
            'booking': ['réserv', 'table', 'book', 'reservation', 'place']
        }
        
    def detect_language(self, text: str) -> str:
        french_words = ['le', 'la', 'des', 'vous', 'avec', 'pour', 'avez', 'êtes']
        english_words = ['the', 'you', 'are', 'have', 'with', 'what', 'your']
        
        text_lower = text.lower()
        fr_count = sum(1 for word in french_words if word in text_lower)
        en_count = sum(1 for word in english_words if word in text_lower)
        
        # Check accents
        if any(c in text_lower for c in 'àéèêçù'):
            return 'fr'
            
        return 'fr' if fr_count >= en_count else 'en'
    
    def classify_intent(self, text: str) -> str:
        text_lower = text.lower()
        
        for intent, keywords in self.intent_patterns.items():
            if any(keyword in text_lower for keyword in keywords):
                return intent
        
        return 'fallback'

nlp = SimpleNLP()

# Data functions
def load_csv(file_path: str) -> List[Dict]:
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            return list(csv.DictReader(f))
    except:
        return []

def log_conversation(event: str, text: str, **kwargs):
    log_entry = {
        "timestamp": datetime.now().isoformat(),
        "event": event,
        "text": text,
        **kwargs
    }
    
    os.makedirs("logs", exist_ok=True)
    with open("logs/conversations.jsonl", "a", encoding="utf-8") as f:
        f.write(json.dumps(log_entry, ensure_ascii=False) + "\n")

# Responses
RESPONSES = {
    'menu': {
        'fr': "🍽️ Voici notre sélection :\n{items}\n\nVenez découvrir notre carte complète !",
        'en': "🍽️ Here's our selection:\n{items}\n\nCome discover our full menu!"
    },
    'promos': {
        'fr': "🎉 Nos promotions actuelles :\n{promos}",
        'en': "🎉 Our current promotions:\n{promos}"
    },
    'horaires': {
        'fr': "🕐 Nous sommes {status} aujourd'hui.\n{hours}",
        'en': "🕐 We are {status} today.\n{hours}"
    },
    'booking': {
        'fr': "📅 Pour réserver :\n• Date (AAAA-MM-JJ)\n• Heure (HH:MM)\n• Nombre de personnes\n• Nom et téléphone",
        'en': "📅 To book:\n• Date (YYYY-MM-DD)\n• Time (HH:MM)\n• Number of people\n• Name and phone"
    },
    'fallback': {
        'fr': "Je peux vous aider avec :\n🍽️ Le menu\n🕐 Les horaires\n🎉 Les promotions\n📅 Les réservations\n\nQue souhaitez-vous ?",
        'en': "I can help with:\n🍽️ Menu\n🕐 Hours\n🎉 Promotions\n📅 Reservations\n\nWhat do you need?"
    }
}

# Endpoints
@app.get("/")
async def root():
    return {
        "message": "🍽️ Iwacu Chatbot API is running!",
        "version": "1.0.0",
        "test_widget": "http://localhost:8080/widget",
        "endpoints": ["/health", "/menu", "/promos", "/horaires", "/chat", "/booking"]
    }

@app.get("/health")
async def health():
    return {"status": "ok", "timestamp": datetime.now().isoformat()}

@app.get("/menu")
async def get_menu():
    items = load_csv("data/menu.csv")
    return {"items": items}

@app.get("/promos")
async def get_promos():
    promos = load_csv("data/promos.csv")
    now = datetime.now()
    current_day = now.strftime('%A').lower()
    current_time = now.time()
    
    active = []
    today_promos = []
    
    for promo in promos:
        if promo.get('day') in [current_day, 'all']:
            today_promos.append(promo)
            
            try:
                start = datetime.strptime(promo.get('start_time', ''), '%H:%M').time()
                end = datetime.strptime(promo.get('end_time', ''), '%H:%M').time()
                if start <= current_time <= end:
                    active.append(promo)
            except:
                pass
    
    return {"active": active, "today": today_promos}

@app.get("/horaires")
async def get_horaires():
    hours = load_csv("data/hours.csv")
    return {"week": hours}

@app.get("/horaires/today")
async def get_today_hours():
    hours = load_csv("data/hours.csv")
    today = datetime.now().strftime('%A').lower()
    
    for hour in hours:
        if hour.get('day') == today:
            return {
                "status": "open",
                "open_time": hour.get('open'),
                "close_time": hour.get('close')
            }
    
    return {"status": "unknown"}

@app.post("/chat")
async def chat(message: ChatMessage):
    try:
        # Log user message
        log_conversation("user", message.text, sender=message.sender)
        
        # Detect language and intent
        lang = nlp.detect_language(message.text)
        intent = nlp.classify_intent(message.text)
        
        # Generate response
        if intent == "menu":
            items = load_csv("data/menu.csv")[:3]  # Top 3
            items_text = "\n".join([f"• {i.get('name')} - €{i.get('price')}" for i in items])
            reply = RESPONSES['menu'][lang].format(items=items_text)
            
        elif intent == "promos":
            promos_data = await get_promos()
            if promos_data['active']:
                promos_text = "\n".join([f"• {p.get('name')}: {p.get('notes')}" for p in promos_data['active']])
            else:
                promos_text = "Aucune promo active" if lang == 'fr' else "No active promotions"
            reply = RESPONSES['promos'][lang].format(promos=promos_text)
            
        elif intent == "horaires":
            hours_info = await get_today_hours()
            status = "ouverts" if lang == 'fr' else "open"
            hours_text = ""
            if hours_info.get('open_time'):
                hours_text = f"\n⏰ {hours_info['open_time']} - {hours_info['close_time']}"
            reply = RESPONSES['horaires'][lang].format(status=status, hours=hours_text)
            
        elif intent == "booking":
            reply = RESPONSES['booking'][lang]
            
        else:
            reply = RESPONSES['fallback'][lang]
        
        # Log bot response
        log_conversation("bot", reply, intent=intent, lang=lang)
        
        return ChatResponse(reply=reply, intent=intent, lang=lang)
        
    except Exception as e:
        return ChatResponse(
            reply="Erreur technique, veuillez réessayer.",
            intent="error", 
            lang="fr"
        )

@app.post("/booking")
async def create_booking(booking: BookingRequest):
    try:
        # Validate date
        booking_date = datetime.strptime(booking.date, "%Y-%m-%d")
        if booking_date.date() <= datetime.now().date():
            raise HTTPException(400, "Date must be in the future")
        
        # Generate booking ID
        booking_id = str(uuid.uuid4())[:8].upper()
        
        # Save to CSV
        os.makedirs("data", exist_ok=True)
        with open("data/bookings.csv", "a", newline="", encoding="utf-8") as f:
            if os.path.getsize("data/bookings.csv") == 0:
                f.write("booking_id,date,time,party_size,name,phone,area,notes,created_at\n")
            
            f.write(f"{booking_id},{booking.date},{booking.time},{booking.party_size},"
                   f"{booking.name},{booking.phone},{booking.area},{booking.notes},"
                   f"{datetime.now().isoformat()}\n")
        
        # Generate ICS
        booking_datetime = datetime.strptime(f"{booking.date} {booking.time}", "%Y-%m-%d %H:%M")
        end_datetime = booking_datetime + timedelta(minutes=90)
        
        ics_content = f"""BEGIN:VCALENDAR
VERSION:2.0
PRODID:-//Iwacu//Reservation//EN
BEGIN:VEVENT
UID:{booking_id}@iwacu.restaurant
DTSTART:{booking_datetime.strftime('%Y%m%dT%H%M%S')}
DTEND:{end_datetime.strftime('%Y%m%dT%H%M%S')}
SUMMARY:Réservation Iwacu - {booking.name}
DESCRIPTION:Table pour {booking.party_size} personne(s)
LOCATION:Restaurant Iwacu
END:VEVENT
END:VCALENDAR"""
        
        os.makedirs("ics_files", exist_ok=True)
        with open(f"ics_files/{booking_id}.ics", "w", encoding="utf-8") as f:
            f.write(ics_content)
        
        return {
            "ok": True,
            "booking_id": booking_id,
            "storage": "csv",
            "ics_url": f"/booking/ics/{booking_id}"
        }
        
    except ValueError:
        raise HTTPException(400, "Invalid date format")
    except Exception as e:
        raise HTTPException(500, f"Booking failed: {str(e)}")

@app.get("/booking/ics/{booking_id}")
async def download_ics(booking_id: str):
    ics_path = f"ics_files/{booking_id}.ics"
    
    if not os.path.exists(ics_path):
        raise HTTPException(404, "ICS file not found")
    
    with open(ics_path, "r", encoding="utf-8") as f:
        content = f.read()
    
    return Response(
        content=content,
        media_type="text/calendar",
        headers={"Content-Disposition": f"attachment; filename=reservation_{booking_id}.ics"}
    )

@app.get("/widget", response_class=HTMLResponse)
async def widget():
    return """<!DOCTYPE html>
<html lang="fr">
<head>
    <title>Iwacu Chat</title>
    <meta charset="utf-8">
    <style>
        body { font-family: Arial, sans-serif; margin: 0; padding: 20px; background: #f5f5f5; }
        .chat-container { max-width: 600px; margin: 0 auto; background: white; border-radius: 10px; overflow: hidden; box-shadow: 0 4px 15px rgba(0,0,0,0.1); }
        .chat-header { background: linear-gradient(135deg, #2c5aa0, #1e4080); color: white; padding: 20px; text-align: center; }
        .chat-header h1 { margin: 0; font-size: 1.5em; }
        .chat-header p { margin: 5px 0 0 0; opacity: 0.9; }
        .quick-buttons { padding: 15px; background: #f8f9fa; display: flex; flex-wrap: wrap; gap: 10px; }
        .quick-btn { background: #e9ecef; border: none; padding: 8px 15px; border-radius: 20px; cursor: pointer; font-size: 14px; }
        .quick-btn:hover { background: #2c5aa0; color: white; }
        .messages { height: 400px; overflow-y: auto; padding: 20px; }
        .message { margin: 10px 0; padding: 12px 18px; border-radius: 18px; max-width: 80%; }
        .user-message { background: #007bff; color: white; margin-left: auto; }
        .bot-message { background: #e9ecef; }
        .input-area { padding: 20px; border-top: 1px solid #eee; display: flex; gap: 10px; }
        .input-area input { flex: 1; padding: 12px; border: 1px solid #ddd; border-radius: 25px; font-size: 14px; }
        .input-area button { padding: 12px 24px; background: #2c5aa0; color: white; border: none; border-radius: 25px; cursor: pointer; }
        .input-area button:hover { background: #1e4080; }
    </style>
</head>
<body>
    <div class="chat-container">
        <div class="chat-header">
            <h1>🍽️ Iwacu Assistant</h1>
            <p>Bonjour ! Comment puis-je vous aider ?</p>
        </div>
        
        <div class="quick-buttons">
            <button class="quick-btn" onclick="sendQuick('Menu du jour')">📋 Menu</button>
            <button class="quick-btn" onclick="sendQuick('Horaires aujourd\\'hui')">🕐 Horaires</button>
            <button class="quick-btn" onclick="sendQuick('Promotions actuelles')">🎉 Promos</button>
            <button class="quick-btn" onclick="sendQuick('Réservation')">📅 Réserver</button>
        </div>
        
        <div class="messages" id="messages">
            <div class="message bot-message">
                👋 Bienvenue chez Iwacu ! Je peux vous renseigner sur notre menu, horaires, promotions et réservations.
            </div>
        </div>
        
        <div class="input-area">
            <input type="text" id="messageInput" placeholder="Tapez votre message..." onkeypress="handleEnter(event)">
            <button onclick="sendMessage()">Envoyer</button>
        </div>
    </div>

    <script>
        async function sendMessage(text = null) {
            const input = document.getElementById('messageInput');
            const messages = document.getElementById('messages');
            const messageText = text || input.value.trim();
            
            if (!messageText) return;
            
            // Add user message
            addMessage(messageText, 'user-message');
            input.value = '';
            
            try {
                const response = await fetch('/chat', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ text: messageText, sender: 'web_widget' })
                });
                
                const data = await response.json();
                addMessage(data.reply, 'bot-message');
                
            } catch (error) {
                addMessage('❌ Erreur de connexion. Veuillez réessayer.', 'bot-message');
            }
        }
        
        function addMessage(text, className) {
            const messages = document.getElementById('messages');
            const msg = document.createElement('div');
            msg.className = `message ${className}`;
            msg.innerHTML = text.replace(/\\n/g, '<br>');
            messages.appendChild(msg);
            messages.scrollTop = messages.scrollHeight;
        }
        
        function sendQuick(message) {
            sendMessage(message);
        }
        
        function handleEnter(event) {
            if (event.key === 'Enter') {
                sendMessage();
            }
        }
    </script>
</body>
</html>"""

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("API_PORT", 8080))
    print(f"🚀 Démarrage Iwacu API sur le port {port}")
    print(f"🌐 Widget: http://localhost:{port}/widget")
    uvicorn.run(app, host="0.0.0.0", port=port)
