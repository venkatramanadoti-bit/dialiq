from fastapi import FastAPI, Depends, HTTPException, Request, Form, File, UploadFile, WebSocket, WebSocketDisconnect, status
from fastapi.security import OAuth2PasswordRequestForm
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from sqlalchemy import func, desc
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any
import os
import json
import csv
import io
import uuid
import asyncio
from dotenv import load_dotenv

load_dotenv()

from database import engine, get_db, init_db
from models import Base, User, UserRole, AIAgent, Lead, Campaign, CallLog, CallStatus, LeadDisposition, CampaignStatus, WalletTransaction, WebhookConfig, DLTConfig, PricingPlan, AgentLanguage
from schemas import *
from auth import get_current_user, get_current_active_user, require_admin, create_access_token, verify_password, get_password_hash
from services.ai_service import ai_service
from services.telephony_service import telephony_service
from services.billing_service import billing_service
from services.phonepe_service import phonepe_service

# Create tables
init_db()

# Initialize default pricing plans
def init_pricing_plans(db: Session):
    plans = [
        PricingPlan(
            name="starter",
            display_name="Starter",
            description="Perfect for small teams getting started with AI calling",
            price=5000,
            credits=500,
            features=["500 calling minutes", "1 AI agent", "Basic analytics", "Email support", "CSV lead upload"],
            is_popular=False,
            sort_order=1
        ),
        PricingPlan(
            name="growth",
            display_name="Growth",
            description="Best for growing businesses scaling their outreach",
            price=15000,
            credits=2000,
            features=["2000 calling minutes", "5 AI agents", "Advanced analytics", "Priority support", "CRM integrations", "Webhooks", "Custom voices"],
            is_popular=True,
            sort_order=2
        ),
        PricingPlan(
            name="enterprise",
            display_name="Enterprise",
            description="For large organizations with high-volume calling needs",
            price=50000,
            credits=10000,
            features=["10000 calling minutes", "Unlimited AI agents", "Custom integrations", "Dedicated support", "SLA guarantee", "White-label option", "On-premise deployment"],
            is_popular=False,
            sort_order=3
        )
    ]
    for plan in plans:
        existing = db.query(PricingPlan).filter(PricingPlan.name == plan.name).first()
        if not existing:
            db.add(plan)
    db.commit()

# Initialize database with default plans
db = next(get_db())
init_pricing_plans(db)
db.close()

app = FastAPI(
    title="DialIQ API",
    description="AI Telecalling Platform - Best for lead generation and data-driven campaigns",
    version="1.0.0"
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Static files and templates
import os
frontend_dir = os.path.join(os.path.dirname(__file__), "..", "frontend")
app.mount("/static", StaticFiles(directory=frontend_dir), name="static")
templates = Jinja2Templates(directory=frontend_dir)

# WebSocket connections for real-time updates
active_websockets: Dict[int, List[WebSocket]] = {}

async def notify_user(user_id: int, message: dict):
    if user_id in active_websockets:
        for ws in active_websockets[user_id]:
            try:
                await ws.send_json(message)
            except:
                pass

# ==================== AUTH ROUTES ====================

@app.post("/api/auth/register", response_model=Token)
async def register(user_data: UserCreate, db: Session = Depends(get_db)):
    existing = db.query(User).filter(User.email == user_data.email).first()
    if existing:
        raise HTTPException(status_code=400, detail="Email already registered")

    hashed_password = get_password_hash(user_data.password)
    user = User(
        email=user_data.email,
        hashed_password=hashed_password,
        full_name=user_data.full_name,
        company_name=user_data.company_name,
        phone=user_data.phone,
        wallet_balance=0.0  # Start with 0, must add credits
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    access_token = create_access_token(data={"sub": user.id})
    return Token(access_token=access_token, user=UserResponse.from_orm(user))

@app.post("/api/auth/login", response_model=Token)
async def login(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == form_data.username).first()
    if not user or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Invalid credentials")

    user.last_login = datetime.utcnow()
    db.commit()

    access_token = create_access_token(data={"sub": user.id})
    return Token(access_token=access_token, user=UserResponse.from_orm(user))

@app.get("/api/auth/me", response_model=UserResponse)
async def get_me(current_user: User = Depends(get_current_active_user)):
    return current_user

@app.websocket("/ws/{user_id}")
async def websocket_endpoint(websocket: WebSocket, user_id: int):
    await websocket.accept()
    if user_id not in active_websockets:
        active_websockets[user_id] = []
    active_websockets[user_id].append(websocket)
    try:
        while True:
            data = await websocket.receive_text()
            # Echo for heartbeat
            await websocket.send_text("pong")
    except WebSocketDisconnect:
        active_websockets[user_id].remove(websocket)

# ==================== AI AGENT ROUTES ====================

@app.post("/api/agents", response_model=AIAgentResponse)
async def create_agent(agent_data: AIAgentCreate, current_user: User = Depends(get_current_active_user), db: Session = Depends(get_db)):
    agent = AIAgent(
        user_id=current_user.id,
        name=agent_data.name,
        description=agent_data.description,
        system_prompt=agent_data.system_prompt,
        greeting_message=agent_data.greeting_message,
        objection_handling=[obj.dict() for obj in agent_data.objection_handling],
        voice_id=agent_data.voice_id,
        language=agent_data.language,
        speech_rate=agent_data.speech_rate,
        pitch=agent_data.pitch,
        volume=agent_data.volume,
        background_ambiance=agent_data.background_ambiance,
        transfer_number=agent_data.transfer_number,
        transfer_enabled=agent_data.transfer_enabled,
        knowledge_base=[kb.dict() for kb in agent_data.knowledge_base]
    )
    db.add(agent)
    db.commit()
    db.refresh(agent)
    return agent

@app.get("/api/agents", response_model=List[AIAgentResponse])
async def list_agents(current_user: User = Depends(get_current_active_user), db: Session = Depends(get_db)):
    return db.query(AIAgent).filter(AIAgent.user_id == current_user.id, AIAgent.is_active == True).all()

@app.get("/api/agents/{agent_id}", response_model=AIAgentResponse)
async def get_agent(agent_id: int, current_user: User = Depends(get_current_active_user), db: Session = Depends(get_db)):
    agent = db.query(AIAgent).filter(AIAgent.id == agent_id, AIAgent.user_id == current_user.id).first()
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    return agent

@app.put("/api/agents/{agent_id}", response_model=AIAgentResponse)
async def update_agent(agent_id: int, agent_data: AIAgentUpdate, current_user: User = Depends(get_current_active_user), db: Session = Depends(get_db)):
    agent = db.query(AIAgent).filter(AIAgent.id == agent_id, AIAgent.user_id == current_user.id).first()
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")

    update_data = agent_data.dict(exclude_unset=True)
    if "objection_handling" in update_data and update_data["objection_handling"]:
        update_data["objection_handling"] = [obj.dict() for obj in update_data["objection_handling"]]
    if "knowledge_base" in update_data and update_data["knowledge_base"]:
        update_data["knowledge_base"] = [kb.dict() for kb in update_data["knowledge_base"]]

    for key, value in update_data.items():
        setattr(agent, key, value)
    agent.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(agent)
    return agent

@app.delete("/api/agents/{agent_id}")
async def delete_agent(agent_id: int, current_user: User = Depends(get_current_active_user), db: Session = Depends(get_db)):
    agent = db.query(AIAgent).filter(AIAgent.id == agent_id, AIAgent.user_id == current_user.id).first()
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    agent.is_active = False
    db.commit()
    return {"message": "Agent deleted"}

# ==================== LEAD/CRM ROUTES ====================

@app.post("/api/leads", response_model=LeadResponse)
async def create_lead(lead_data: LeadCreate, current_user: User = Depends(get_current_active_user), db: Session = Depends(get_db)):
    lead = Lead(
        user_id=current_user.id,
        name=lead_data.name,
        phone=lead_data.phone,
        email=lead_data.email,
        custom_fields=lead_data.custom_fields
    )
    db.add(lead)
    db.commit()
    db.refresh(lead)
    return lead

@app.post("/api/leads/bulk", response_model=List[LeadResponse])
async def bulk_create_leads(leads_data: LeadBulkCreate, current_user: User = Depends(get_current_active_user), db: Session = Depends(get_db)):
    leads = []
    for lead_data in leads_data.leads:
        lead = Lead(
            user_id=current_user.id,
            campaign_id=leads_data.campaign_id,
            name=lead_data.name,
            phone=lead_data.phone,
            email=lead_data.email,
            custom_fields=lead_data.custom_fields
        )
        leads.append(lead)
    db.add_all(leads)
    db.commit()
    for lead in leads:
        db.refresh(lead)
    return leads

@app.post("/api/leads/upload-csv")
async def upload_leads_csv(
    file: UploadFile = File(...),
    campaign_id: Optional[int] = Form(None),
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    content = await file.read()
    decoded = content.decode('utf-8')
    reader = csv.DictReader(io.StringIO(decoded))

    leads = []
    for row in reader:
        phone = row.get('phone') or row.get('Phone') or row.get('mobile') or row.get('Mobile')
        if not phone:
            continue

        custom_fields = {k: v for k, v in row.items() if k.lower() not in ['name', 'phone', 'email', 'mobile']}

        lead = Lead(
            user_id=current_user.id,
            campaign_id=campaign_id,
            name=row.get('name') or row.get('Name'),
            phone=phone,
            email=row.get('email') or row.get('Email'),
            custom_fields=custom_fields
        )
        leads.append(lead)

    db.add_all(leads)
    db.commit()
    for lead in leads:
        db.refresh(lead)

    # Update campaign lead count
    if campaign_id:
        campaign = db.query(Campaign).filter(Campaign.id == campaign_id, Campaign.user_id == current_user.id).first()
        if campaign:
            campaign.total_leads = len(leads)
            db.commit()

    return {"message": f"Uploaded {len(leads)} leads", "leads": [LeadResponse.from_orm(l) for l in leads]}

@app.get("/api/leads", response_model=List[LeadResponse])
async def list_leads(
    campaign_id: Optional[int] = None,
    disposition: Optional[LeadDisposition] = None,
    skip: int = 0,
    limit: int = 100,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    query = db.query(Lead).filter(Lead.user_id == current_user.id)
    if campaign_id:
        query = query.filter(Lead.campaign_id == campaign_id)
    if disposition:
        query = query.filter(Lead.disposition == disposition)
    return query.offset(skip).limit(limit).all()

@app.get("/api/leads/{lead_id}", response_model=LeadResponse)
async def get_lead(lead_id: int, current_user: User = Depends(get_current_active_user), db: Session = Depends(get_db)):
    lead = db.query(Lead).filter(Lead.id == lead_id, Lead.user_id == current_user.id).first()
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")
    return lead

@app.put("/api/leads/{lead_id}", response_model=LeadResponse)
async def update_lead(lead_id: int, lead_data: LeadUpdate, current_user: User = Depends(get_current_active_user), db: Session = Depends(get_db)):
    lead = db.query(Lead).filter(Lead.id == lead_id, Lead.user_id == current_user.id).first()
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")

    update_data = lead_data.dict(exclude_unset=True)
    for key, value in update_data.items():
        setattr(lead, key, value)
    lead.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(lead)
    return lead

# ==================== CAMPAIGN ROUTES ====================

@app.post("/api/campaigns", response_model=CampaignResponse)
async def create_campaign(campaign_data: CampaignCreate, current_user: User = Depends(get_current_active_user), db: Session = Depends(get_db)):
    # Verify agent belongs to user
    agent = db.query(AIAgent).filter(AIAgent.id == campaign_data.agent_id, AIAgent.user_id == current_user.id).first()
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")

    # Count leads in campaign
    lead_count = db.query(Lead).filter(Lead.campaign_id == campaign_data.id if hasattr(campaign_data, 'id') else False).count()

    campaign = Campaign(
        user_id=current_user.id,
        agent_id=campaign_data.agent_id,
        name=campaign_data.name,
        description=campaign_data.description,
        start_time=campaign_data.start_time,
        end_time=campaign_data.end_time,
        timezone=campaign_data.timezone,
        concurrent_calls=campaign_data.concurrent_calls,
        retry_attempts=campaign_data.retry_attempts,
        retry_interval=campaign_data.retry_interval,
        retry_on=campaign_data.retry_on,
        total_leads=lead_count
    )
    db.add(campaign)
    db.commit()
    db.refresh(campaign)
    return campaign

@app.get("/api/campaigns", response_model=List[CampaignResponse])
async def list_campaigns(current_user: User = Depends(get_current_active_user), db: Session = Depends(get_db)):
    return db.query(Campaign).filter(Campaign.user_id == current_user.id).order_by(desc(Campaign.created_at)).all()

@app.get("/api/campaigns/{campaign_id}", response_model=CampaignResponse)
async def get_campaign(campaign_id: int, current_user: User = Depends(get_current_active_user), db: Session = Depends(get_db)):
    campaign = db.query(Campaign).filter(Campaign.id == campaign_id, Campaign.user_id == current_user.id).first()
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")
    return campaign

@app.put("/api/campaigns/{campaign_id}", response_model=CampaignResponse)
async def update_campaign(campaign_id: int, campaign_data: CampaignUpdate, current_user: User = Depends(get_current_active_user), db: Session = Depends(get_db)):
    campaign = db.query(Campaign).filter(Campaign.id == campaign_id, Campaign.user_id == current_user.id).first()
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")

    update_data = campaign_data.dict(exclude_unset=True)
    for key, value in update_data.items():
        setattr(campaign, key, value)
    campaign.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(campaign)
    return campaign

@app.post("/api/campaigns/{campaign_id}/start")
async def start_campaign(campaign_id: int, current_user: User = Depends(get_current_active_user), db: Session = Depends(get_db)):
    campaign = db.query(Campaign).filter(Campaign.id == campaign_id, Campaign.user_id == current_user.id).first()
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")

    campaign.status = CampaignStatus.RUNNING
    campaign.start_time = datetime.utcnow()
    db.commit()

    # Start background task for campaign execution
    asyncio.create_task(run_campaign(campaign_id, current_user.id))

    return {"message": "Campaign started", "campaign_id": campaign_id}

@app.post("/api/campaigns/{campaign_id}/pause")
async def pause_campaign(campaign_id: int, current_user: User = Depends(get_current_active_user), db: Session = Depends(get_db)):
    campaign = db.query(Campaign).filter(Campaign.id == campaign_id, Campaign.user_id == current_user.id).first()
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")
    campaign.status = CampaignStatus.PAUSED
    db.commit()
    return {"message": "Campaign paused"}

@app.post("/api/campaigns/{campaign_id}/stop")
async def stop_campaign(campaign_id: int, current_user: User = Depends(get_current_active_user), db: Session = Depends(get_db)):
    campaign = db.query(Campaign).filter(Campaign.id == campaign_id, Campaign.user_id == current_user.id).first()
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")
    campaign.status = CampaignStatus.COMPLETED
    campaign.end_time = datetime.utcnow()
    db.commit()
    return {"message": "Campaign stopped"}

# ==================== CALL ROUTES ====================

@app.post("/api/calls/simulate", response_model=SimulateCallResponse)
async def simulate_call(request: SimulateCallRequest, current_user: User = Depends(get_current_active_user), db: Session = Depends(get_db)):
    """Simulate a call for testing (demo mode)"""
    agent = db.query(AIAgent).filter(AIAgent.id == request.agent_id, AIAgent.user_id == current_user.id).first()
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")

    agent_config = {
        "id": agent.id,
        "name": agent.name,
        "company": current_user.company_name or "DialIQ",
        "system_prompt": agent.system_prompt,
        "greeting_message": agent.greeting_message,
        "objection_handling": agent.objection_handling,
        "knowledge_base": agent.knowledge_base,
        "transfer_number": agent.transfer_number,
        "transfer_enabled": agent.transfer_enabled,
        "language": agent.language.value if agent.language else "en-IN"
    }

    # Simulate conversation
    conversation_history = []
    transcript = []

    # AI greeting
    greeting_result = await ai_service.generate_response(agent_config, [], "")
    conversation_history.append({"speaker": "ai", "text": greeting_result["text"], "timestamp": datetime.now().timestamp()})
    transcript.append(TranscriptEntry(speaker="ai", text=greeting_result["text"], timestamp=0))

    # Simulate a few exchanges
    for i in range(3):
        # Simulated customer responses
        customer_responses = [
            "Hello, who is this?",
            "What are you calling about?",
            "I'm not interested, thanks.",
            "How much does it cost?",
            "Can you call me back later?",
            "Tell me more about your service."
        ]
        import random
        customer_text = random.choice(customer_responses)

        conversation_history.append({"speaker": "customer", "text": customer_text, "timestamp": datetime.now().timestamp()})
        transcript.append(TranscriptEntry(speaker="customer", text=customer_text, timestamp=len(transcript) * 5))

        ai_result = await ai_service.generate_response(agent_config, conversation_history, customer_text)
        conversation_history.append({"speaker": "ai", "text": ai_result["text"], "timestamp": datetime.now().timestamp()})
        transcript.append(TranscriptEntry(speaker="ai", text=ai_result["text"], timestamp=len(transcript) * 5))

        if ai_result["should_transfer"] or ai_result["disposition"] in ["hot_lead", "not_interested"]:
            break

    # Create call log
    duration = random.randint(30, 180)
    cost = billing_service.calculate_call_cost(duration)

    call_log = CallLog(
        user_id=current_user.id,
        agent_id=agent.id,
        phone_number=request.phone_number,
        status=CallStatus.COMPLETED,
        direction="outbound",
        duration=duration,
        cost=cost,
        transcript=[t.dict() for t in transcript],
        sentiment_score=ai_result["sentiment_score"],
        disposition=ai_result["disposition"],
        summary=f"Simulated call with {len(transcript)} exchanges",
        started_at=datetime.utcnow() - timedelta(seconds=duration),
        answered_at=datetime.utcnow() - timedelta(seconds=duration-5),
        ended_at=datetime.utcnow()
    )
    db.add(call_log)
    db.commit()
    db.refresh(call_log)

    # Deduct from wallet
    try:
        billing_service.deduct_balance(db, current_user.id, cost, f"Simulated call to {request.phone_number}", str(call_log.id))
    except ValueError:
        pass  # Ignore insufficient balance in demo

    return SimulateCallResponse(
        call_id=call_log.id,
        transcript=transcript,
        duration=duration,
        cost=cost,
        sentiment_score=ai_result["sentiment_score"],
        disposition=ai_result["disposition"],
        summary=call_log.summary,
        recording_url=call_log.recording_url
    )

@app.get("/api/calls", response_model=List[CallLogResponse])
async def list_calls(
    campaign_id: Optional[int] = None,
    status: Optional[CallStatus] = None,
    skip: int = 0,
    limit: int = 100,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    query = db.query(CallLog).filter(CallLog.user_id == current_user.id)
    if campaign_id:
        query = query.filter(CallLog.campaign_id == campaign_id)
    if status:
        query = query.filter(CallLog.status == status)
    return query.order_by(desc(CallLog.created_at)).offset(skip).limit(limit).all()

@app.get("/api/calls/{call_id}", response_model=CallLogResponse)
async def get_call(call_id: int, current_user: User = Depends(get_current_active_user), db: Session = Depends(get_db)):
    call = db.query(CallLog).filter(CallLog.id == call_id, CallLog.user_id == current_user.id).first()
    if not call:
        raise HTTPException(status_code=404, detail="Call not found")
    return call

# ==================== WALLET & BILLING ROUTES ====================

@app.get("/api/wallet/balance", response_model=WalletBalance)
async def get_wallet_balance(current_user: User = Depends(get_current_active_user), db: Session = Depends(get_db)):
    balance = billing_service.get_wallet_balance(db, current_user.id)
    return WalletBalance(
        balance=balance,
        currency="INR",
        per_minute_rate=billing_service.get_per_minute_rate()
    )

@app.get("/api/wallet/transactions", response_model=List[WalletTransactionResponse])
async def get_transactions(
    skip: int = 0,
    limit: int = 50,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    return billing_service.get_transactions(db, current_user.id, limit, skip)

@app.get("/api/wallet/plans", response_model=List[PricingPlanResponse])
async def get_pricing_plans(db: Session = Depends(get_db)):
    return billing_service.get_pricing_plans(db)

@app.post("/api/wallet/phonepe/initiate")
async def initiate_phonepe_payment(
    request: AddCreditsRequest,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Initiate PhonePe payment for wallet top-up"""
    plan = None
    if request.plan_id:
        plan = db.query(PricingPlan).filter(PricingPlan.id == request.plan_id).first()
        if not plan:
            raise HTTPException(status_code=404, detail="Plan not found")
        amount = plan.price
    else:
        amount = request.amount

    merchant_transaction_id = f"DIALIQ_{current_user.id}_{uuid.uuid4().hex[:12]}"

    # Get base URL from request headers or config
    base_url = os.getenv("BASE_URL", "http://localhost:8000")
    callback_url = f"{base_url}/api/wallet/phonepe/callback"
    redirect_url = f"{base_url}/wallet?payment=success"

    result = await phonepe_service.initiate_payment(
        merchant_transaction_id=merchant_transaction_id,
        amount=amount,
        callback_url=callback_url,
        redirect_url=redirect_url,
        user_id=current_user.id,
        plan_id=request.plan_id,
        mobile_number=current_user.phone,
        email=current_user.email
    )

    if result.get("success") and result.get("data", {}).get("instrumentResponse", {}).get("redirectInfo", {}).get("url"):
        redirect_url = result["data"]["instrumentResponse"]["redirectInfo"]["url"]
        return {
            "success": True,
            "redirect_url": redirect_url,
            "merchant_transaction_id": merchant_transaction_id
        }
    else:
        raise HTTPException(status_code=400, detail=result.get("message", "Payment initiation failed"))

@app.post("/api/wallet/phonepe/callback")
async def phonepe_callback(request: Request, db: Session = Depends(get_db)):
    """Handle PhonePe payment callback"""
    form_data = await request.form()
    callback_data = dict(form_data)

    # Process callback
    processed = phonepe_service.process_payment_callback(callback_data)

    if processed.get("success") and processed.get("data", {}).get("state") == "COMPLETED":
        data = processed["data"]
        merchant_transaction_id = data.get("merchantTransactionId")
        phonepe_transaction_id = data.get("transactionId")
        amount_paise = data.get("amount", 0)
        amount = amount_paise / 100

        # Extract user_id from merchant_transaction_id
        try:
            user_id = int(merchant_transaction_id.split("_")[1])
        except:
            return {"status": "error", "message": "Invalid transaction ID"}

        # Credit wallet
        await phonepe_service.handle_payment_success(
            db=db,
            user_id=user_id,
            merchant_transaction_id=merchant_transaction_id,
            phonepe_transaction_id=phonepe_transaction_id,
            amount=amount
        )

    return {"status": "received"}

@app.get("/api/wallet/phonepe/status/{merchant_transaction_id}")
async def check_payment_status(merchant_transaction_id: str, current_user: User = Depends(get_current_active_user), db: Session = Depends(get_db)):
    """Check payment status"""
    result = await phonepe_service.check_payment_status(merchant_transaction_id)

    if result.get("success") and result.get("data", {}).get("state") == "COMPLETED":
        data = result["data"]
        amount_paise = data.get("amount", 0)
        amount = amount_paise / 100

        # Verify this transaction belongs to current user
        try:
            txn_user_id = int(merchant_transaction_id.split("_")[1])
            if txn_user_id != current_user.id:
                raise HTTPException(status_code=403, detail="Unauthorized")
        except:
            pass

        # Check if already processed
        existing = db.query(WalletTransaction).filter(
            WalletTransaction.reference_id == merchant_transaction_id,
            WalletTransaction.user_id == current_user.id
        ).first()

        if not existing:
            await phonepe_service.handle_payment_success(
                db=db,
                user_id=current_user.id,
                merchant_transaction_id=merchant_transaction_id,
                phonepe_transaction_id=data.get("transactionId"),
                amount=amount
            )

        return {"status": "success", "message": "Payment verified and wallet credited"}

    return {"status": "pending", "data": result}

@app.get("/api/wallet/invoice/{transaction_id}")
async def download_invoice(transaction_id: int, current_user: User = Depends(get_current_active_user), db: Session = Depends(get_db)):
    """Download GST invoice for transaction"""
    transaction = db.query(WalletTransaction).filter(
        WalletTransaction.id == transaction_id,
        WalletTransaction.user_id == current_user.id
    ).first()
    if not transaction:
        raise HTTPException(status_code=404, detail="Transaction not found")

    user = db.query(User).filter(User.id == current_user.id).first()
    invoice = billing_service.generate_gst_invoice(transaction, user)

    # Return as JSON for frontend to generate PDF
    return invoice

# ==================== ANALYTICS ROUTES ====================

@app.get("/api/analytics/overview", response_model=CallAnalytics)
async def get_analytics_overview(
    days: int = 30,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    since = datetime.utcnow() - timedelta(days=days)

    calls = db.query(CallLog).filter(
        CallLog.user_id == current_user.id,
        CallLog.created_at >= since
    ).all()

    total_calls = len(calls)
    answered_calls = len([c for c in calls if c.status == CallStatus.ANSWERED or c.status == CallStatus.COMPLETED])
    completed_calls = len([c for c in calls if c.status == CallStatus.COMPLETED])
    pickup_rate = (answered_calls / total_calls * 100) if total_calls > 0 else 0

    hot_leads = len([c for c in calls if c.disposition == LeadDisposition.HOT_LEAD])
    callbacks = len([c for c in calls if c.disposition == LeadDisposition.CALLBACK_REQUESTED])
    conversion_rate = (hot_leads / answered_calls * 100) if answered_calls > 0 else 0

    total_duration = sum(c.duration for c in calls)
    avg_duration = total_duration / total_calls if total_calls > 0 else 0
    total_cost = sum(c.cost for c in calls)

    return CallAnalytics(
        total_calls=total_calls,
        answered_calls=answered_calls,
        completed_calls=completed_calls,
        pickup_rate=round(pickup_rate, 2),
        conversion_rate=round(conversion_rate, 2),
        avg_duration=round(avg_duration, 2),
        total_duration=total_duration,
        total_cost=round(total_cost, 2),
        hot_leads=hot_leads,
        callbacks=callbacks
    )

@app.get("/api/analytics/daily", response_model=List[DailyStats])
async def get_daily_analytics(
    days: int = 30,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    since = datetime.utcnow() - timedelta(days=days)

    # Query daily stats
    daily_data = db.query(
        func.date(CallLog.created_at).label('date'),
        func.count(CallLog.id).label('calls'),
        func.sum(func.case([(CallLog.status.in_([CallStatus.ANSWERED, CallStatus.COMPLETED]), 1)], else_=0)).label('answered'),
        func.sum(CallLog.duration).label('duration'),
        func.sum(CallLog.cost).label('cost'),
        func.sum(func.case([(CallLog.disposition == LeadDisposition.HOT_LEAD, 1)], else_=0)).label('hot_leads')
    ).filter(
        CallLog.user_id == current_user.id,
        CallLog.created_at >= since
    ).group_by(func.date(CallLog.created_at)).all()

    stats = []
    for row in daily_data:
        stats.append(DailyStats(
            date=row.date.isoformat() if row.date else "",
            calls=row.calls or 0,
            answered=row.answered or 0,
            duration=row.duration or 0,
            cost=float(row.cost or 0),
            hot_leads=row.hot_leads or 0
        ))

    return stats

# ==================== WEBHOOK ROUTES ====================

@app.post("/api/webhooks", response_model=WebhookConfigResponse)
async def create_webhook(webhook_data: WebhookConfigCreate, current_user: User = Depends(get_current_active_user), db: Session = Depends(get_db)):
    webhook = WebhookConfig(
        user_id=current_user.id,
        name=webhook_data.name,
        url=webhook_data.url,
        events=webhook_data.events,
        secret=webhook_data.secret
    )
    db.add(webhook)
    db.commit()
    db.refresh(webhook)
    return webhook

@app.get("/api/webhooks", response_model=List[WebhookConfigResponse])
async def list_webhooks(current_user: User = Depends(get_current_active_user), db: Session = Depends(get_db)):
    return db.query(WebhookConfig).filter(WebhookConfig.user_id == current_user.id).all()

@app.put("/api/webhooks/{webhook_id}", response_model=WebhookConfigResponse)
async def update_webhook(webhook_id: int, webhook_data: WebhookConfigUpdate, current_user: User = Depends(get_current_active_user), db: Session = Depends(get_db)):
    webhook = db.query(WebhookConfig).filter(WebhookConfig.id == webhook_id, WebhookConfig.user_id == current_user.id).first()
    if not webhook:
        raise HTTPException(status_code=404, detail="Webhook not found")

    update_data = webhook_data.dict(exclude_unset=True)
    for key, value in update_data.items():
        setattr(webhook, key, value)
    webhook.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(webhook)
    return webhook

@app.delete("/api/webhooks/{webhook_id}")
async def delete_webhook(webhook_id: int, current_user: User = Depends(get_current_active_user), db: Session = Depends(get_db)):
    webhook = db.query(WebhookConfig).filter(WebhookConfig.id == webhook_id, WebhookConfig.user_id == current_user.id).first()
    if not webhook:
        raise HTTPException(status_code=404, detail="Webhook not found")
    db.delete(webhook)
    db.commit()
    return {"message": "Webhook deleted"}

# ==================== DLT CONFIG ROUTES ====================

@app.post("/api/dlt-config", response_model=DLTConfigResponse)
async def create_dlt_config(dlt_data: DLTConfigCreate, current_user: User = Depends(get_current_active_user), db: Session = Depends(get_db)):
    existing = db.query(DLTConfig).filter(DLTConfig.user_id == current_user.id).first()
    if existing:
        raise HTTPException(status_code=400, detail="DLT config already exists. Use PUT to update.")

    dlt = DLTConfig(
        user_id=current_user.id,
        header_id=dlt_data.header_id,
        template_id=dlt_data.template_id,
        entity_id=dlt_data.entity_id,
        consent_template_id=dlt_data.consent_template_id
    )
    db.add(dlt)
    db.commit()
    db.refresh(dlt)
    return dlt

@app.get("/api/dlt-config", response_model=DLTConfigResponse)
async def get_dlt_config(current_user: User = Depends(get_current_active_user), db: Session = Depends(get_db)):
    dlt = db.query(DLTConfig).filter(DLTConfig.user_id == current_user.id).first()
    if not dlt:
        raise HTTPException(status_code=404, detail="DLT config not found")
    return dlt

@app.put("/api/dlt-config", response_model=DLTConfigResponse)
async def update_dlt_config(dlt_data: DLTConfigUpdate, current_user: User = Depends(get_current_active_user), db: Session = Depends(get_db)):
    dlt = db.query(DLTConfig).filter(DLTConfig.user_id == current_user.id).first()
    if not dlt:
        dlt = DLTConfig(user_id=current_user.id)
        db.add(dlt)

    update_data = dlt_data.dict(exclude_unset=True)
    for key, value in update_data.items():
        setattr(dlt, key, value)
    dlt.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(dlt)
    return dlt

# ==================== TELEPHONY WEBHOOKS ====================

@app.post("/api/telephony/voice-webhook")
async def voice_webhook(request: Request):
    """Twilio voice webhook - initial call handling"""
    form_data = await request.form()
    call_sid = form_data.get("CallSid")
    from_number = form_data.get("From")
    to_number = form_data.get("To")

    # For demo, return basic TwiML
    response = VoiceResponse()
    response.say("Hello! This is DialIQ AI assistant. How can I help you today?", voice="Polly.Aditi", language="en-IN")
    gather = Gather(input="speech", action="/api/telephony/speech-webhook", method="POST", speech_timeout="auto", language="en-IN")
    gather.say("Please go ahead.", voice="Polly.Aditi", language="en-IN")
    response.append(gather)

    return HTMLResponse(content=str(response), media_type="application/xml")

@app.post("/api/telephony/speech-webhook")
async def speech_webhook(request: Request):
    """Twilio speech webhook - process speech and respond"""
    form_data = await request.form()
    call_sid = form_data.get("CallSid")
    speech_result = form_data.get("SpeechResult", "")
    confidence = float(form_data.get("Confidence", 0))

    # For demo, return simple response
    response = VoiceResponse()
    response.say(f"You said: {speech_result}. Thank you for calling DialIQ. Goodbye!", voice="Polly.Aditi", language="en-IN")
    response.hangup()

    return HTMLResponse(content=str(response), media_type="application/xml")

@app.post("/api/telephony/status-webhook")
async def status_webhook(request: Request):
    """Twilio call status webhook"""
    form_data = await request.form()
    call_sid = form_data.get("CallSid")
    call_status = form_data.get("CallStatus")
    call_duration = form_data.get("CallDuration")

    # Log call status
    print(f"Call {call_sid} status: {call_status}, duration: {call_duration}")

    return {"status": "received"}

@app.post("/api/telephony/recording-webhook")
async def recording_webhook(request: Request):
    """Twilio recording webhook"""
    form_data = await request.form()
    call_sid = form_data.get("CallSid")
    recording_url = form_data.get("RecordingUrl")

    print(f"Recording for call {call_sid}: {recording_url}")

    return {"status": "received"}

# ==================== REAL-TIME VOICE CHAT ====================

@app.websocket("/api/voice-stream/{agent_id}")
async def voice_stream(websocket: WebSocket, agent_id: int, db: Session = Depends(get_db)):
    """WebSocket for real-time voice conversation with AI agent"""
    await websocket.accept()

    agent = db.query(AIAgent).filter(AIAgent.id == agent_id).first()
    if not agent:
        await websocket.close(code=4004)
        return

    agent_config = {
        "id": agent.id,
        "name": agent.name,
        "company": "DialIQ",
        "system_prompt": agent.system_prompt,
        "greeting_message": agent.greeting_message,
        "objection_handling": agent.objection_handling,
        "knowledge_base": agent.knowledge_base,
        "transfer_number": agent.transfer_number,
        "transfer_enabled": agent.transfer_enabled,
        "language": agent.language.value if agent.language else "en-IN"
    }

    conversation_history = []

    try:
        # Send initial greeting
        greeting_result = await ai_service.generate_response(agent_config, [], "")
        conversation_history.append({"speaker": "ai", "text": greeting_result["text"], "timestamp": datetime.now().timestamp()})

        await websocket.send_json({
            "type": "ai_message",
            "text": greeting_result["text"],
            "speaker": "ai"
        })

        while True:
            data = await websocket.receive_json()

            if data.get("type") == "user_speech":
                user_text = data.get("text", "")
                if user_text:
                    conversation_history.append({"speaker": "customer", "text": user_text, "timestamp": datetime.now().timestamp()})

                    ai_result = await ai_service.generate_response(agent_config, conversation_history, user_text)
                    conversation_history.append({"speaker": "ai", "text": ai_result["text"], "timestamp": datetime.now().timestamp()})

                    # Generate TTS audio
                    tts_audio = await ai_service.text_to_speech(ai_result["text"], language=agent_config["language"])
                    audio_base64 = base64.b64encode(tts_audio).decode() if tts_audio else None

                    await websocket.send_json({
                        "type": "ai_message",
                        "text": ai_result["text"],
                        "speaker": "ai",
                        "audio": audio_base64,
                        "sentiment": ai_result["sentiment_score"],
                        "disposition": ai_result["disposition"],
                        "should_transfer": ai_result["should_transfer"]
                    })

            elif data.get("type") == "audio_chunk":
                # Handle real-time audio streaming for STT
                audio_base64 = data.get("audio")
                if audio_base64:
                    audio_bytes = base64.b64decode(audio_base64)
                    stt_result = await ai_service.speech_to_text(audio_bytes, language=agent_config["language"])
                    if stt_result.get("text"):
                        await websocket.send_json({
                            "type": "stt_result",
                            "text": stt_result["text"],
                            "confidence": stt_result["confidence"]
                        })

    except WebSocketDisconnect:
        pass
    except Exception as e:
        print(f"Voice stream error: {e}")
        await websocket.close()

# ==================== FRONTEND ROUTES ====================

@app.get("/", response_class=HTMLResponse)
async def landing_page(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

@app.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    return templates.TemplateResponse("login.html", {"request": request})

@app.get("/register", response_class=HTMLResponse)
async def register_page(request: Request):
    return templates.TemplateResponse("register.html", {"request": request})

@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard(request: Request):
    return templates.TemplateResponse("dashboard.html", {"request": request})

@app.get("/agents", response_class=HTMLResponse)
async def agents_page(request: Request):
    return templates.TemplateResponse("agents.html", {"request": request})

@app.get("/campaigns", response_class=HTMLResponse)
async def campaigns_page(request: Request):
    return templates.TemplateResponse("campaigns.html", {"request": request})

@app.get("/leads", response_class=HTMLResponse)
async def leads_page(request: Request):
    return templates.TemplateResponse("leads.html", {"request": request})

@app.get("/calls", response_class=HTMLResponse)
async def calls_page(request: Request):
    return templates.TemplateResponse("calls.html", {"request": request})

@app.get("/analytics", response_class=HTMLResponse)
async def analytics_page(request: Request):
    return templates.TemplateResponse("analytics.html", {"request": request})

@app.get("/wallet", response_class=HTMLResponse)
async def wallet_page(request: Request):
    return templates.TemplateResponse("wallet.html", {"request": request})

@app.get("/settings", response_class=HTMLResponse)
async def settings_page(request: Request):
    return templates.TemplateResponse("settings.html", {"request": request})

@app.get("/simulator", response_class=HTMLResponse)
async def simulator_page(request: Request):
    return templates.TemplateResponse("simulator.html", {"request": request})

# Admin routes
@app.get("/admin", response_class=HTMLResponse)
async def admin_dashboard(request: Request, current_user: User = Depends(require_admin)):
    return templates.TemplateResponse("admin.html", {"request": request, "user": current_user})

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)