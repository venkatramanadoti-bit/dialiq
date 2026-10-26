from sqlalchemy import Column, Integer, String, Float, Boolean, DateTime, Text, ForeignKey, Enum, JSON
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from database import Base
import enum
from datetime import datetime

class UserRole(str, enum.Enum):
    USER = "user"
    ADMIN = "admin"

class CallStatus(str, enum.Enum):
    INITIATED = "initiated"
    RINGING = "ringing"
    ANSWERED = "answered"
    COMPLETED = "completed"
    BUSY = "busy"
    NO_ANSWER = "no_answer"
    FAILED = "failed"
    VOICEMAIL = "voicemail"

class LeadDisposition(str, enum.Enum):
    HOT_LEAD = "hot_lead"
    CALLBACK_REQUESTED = "callback_requested"
    NOT_INTERESTED = "not_interested"
    VOICEMAIL = "voicemail"
    WRONG_NUMBER = "wrong_number"
    DO_NOT_CALL = "do_not_call"
    FOLLOW_UP = "follow_up"

class CampaignStatus(str, enum.Enum):
    DRAFT = "draft"
    SCHEDULED = "scheduled"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    CANCELLED = "cancelled"

class AgentLanguage(str, enum.Enum):
    ENGLISH_INDIA = "en-IN"
    HINDI = "hi-IN"
    TELUGU = "te-IN"
    TAMIL = "ta-IN"
    HINGLISH = "hi-Latn-IN"

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String(255), unique=True, index=True, nullable=False)
    hashed_password = Column(String(255), nullable=False)
    full_name = Column(String(255))
    company_name = Column(String(255))
    phone = Column(String(20))
    role = Column(Enum(UserRole), default=UserRole.USER)
    wallet_balance = Column(Float, default=1000.0)
    total_credits_purchased = Column(Float, default=0.0)
    is_active = Column(Boolean, default=True)
    is_verified = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    last_login = Column(DateTime(timezone=True))

    # Relationships
    agents = relationship("AIAgent", back_populates="owner")
    campaigns = relationship("Campaign", back_populates="owner")
    leads = relationship("Lead", back_populates="owner")
    calls = relationship("CallLog", back_populates="user")
    transactions = relationship("WalletTransaction", back_populates="user")
    webhooks = relationship("WebhookConfig", back_populates="user")
    dlt_config = relationship("DLTConfig", back_populates="user", uselist=False)

class AIAgent(Base):
    __tablename__ = "ai_agents"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    name = Column(String(255), nullable=False)
    description = Column(Text)
    system_prompt = Column(Text, nullable=False)
    greeting_message = Column(Text)
    objection_handling = Column(JSON)  # List of objection rules
    voice_id = Column(String(100))
    language = Column(Enum(AgentLanguage), default=AgentLanguage.ENGLISH_INDIA)
    speech_rate = Column(Float, default=1.0)
    pitch = Column(Float, default=1.0)
    volume = Column(Float, default=1.0)
    background_ambiance = Column(Boolean, default=False)
    transfer_number = Column(String(20))
    transfer_enabled = Column(Boolean, default=False)
    knowledge_base = Column(JSON)  # FAQs, company docs
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    owner = relationship("User", back_populates="agents")
    campaigns = relationship("Campaign", back_populates="agent")

class Lead(Base):
    __tablename__ = "leads"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    campaign_id = Column(Integer, ForeignKey("campaigns.id"), nullable=True)
    name = Column(String(255))
    phone = Column(String(20), nullable=False, index=True)
    email = Column(String(255))
    custom_fields = Column(JSON)  # Dynamic fields from CSV
    disposition = Column(Enum(LeadDisposition), nullable=True)
    score = Column(Integer, default=0)  # 0-100 lead score
    notes = Column(Text)
    last_called_at = Column(DateTime(timezone=True))
    call_count = Column(Integer, default=0)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    owner = relationship("User", back_populates="leads")
    campaign = relationship("Campaign", back_populates="leads")
    calls = relationship("CallLog", back_populates="lead")

class Campaign(Base):
    __tablename__ = "campaigns"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    agent_id = Column(Integer, ForeignKey("ai_agents.id"), nullable=False)
    name = Column(String(255), nullable=False)
    description = Column(Text)
    status = Column(Enum(CampaignStatus), default=CampaignStatus.DRAFT)
    start_time = Column(DateTime(timezone=True))
    end_time = Column(DateTime(timezone=True))
    timezone = Column(String(50), default="Asia/Kolkata")
    concurrent_calls = Column(Integer, default=5)
    retry_attempts = Column(Integer, default=3)
    retry_interval = Column(Integer, default=300)  # seconds
    retry_on = Column(JSON)  # ["busy", "no_answer"]
    total_leads = Column(Integer, default=0)
    calls_made = Column(Integer, default=0)
    calls_answered = Column(Integer, default=0)
    calls_completed = Column(Integer, default=0)
    total_duration = Column(Integer, default=0)  # seconds
    total_cost = Column(Float, default=0.0)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    owner = relationship("User", back_populates="campaigns")
    agent = relationship("AIAgent", back_populates="campaigns")
    leads = relationship("Lead", back_populates="campaign")
    calls = relationship("CallLog", back_populates="campaign")

class CallLog(Base):
    __tablename__ = "call_logs"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    campaign_id = Column(Integer, ForeignKey("campaigns.id"), nullable=True)
    lead_id = Column(Integer, ForeignKey("leads.id"), nullable=True)
    agent_id = Column(Integer, ForeignKey("ai_agents.id"), nullable=True)
    phone_number = Column(String(20), nullable=False)
    status = Column(Enum(CallStatus), default=CallStatus.INITIATED)
    direction = Column(String(20), default="outbound")  # outbound, inbound
    duration = Column(Integer, default=0)  # seconds
    cost = Column(Float, default=0.0)
    transcript = Column(JSON)  # Full conversation transcript
    recording_url = Column(String(500))
    sentiment_score = Column(Float)  # -1 to 1
    disposition = Column(Enum(LeadDisposition), nullable=True)
    summary = Column(Text)
    started_at = Column(DateTime(timezone=True))
    answered_at = Column(DateTime(timezone=True))
    ended_at = Column(DateTime(timezone=True))
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    user = relationship("User", back_populates="calls")
    campaign = relationship("Campaign", back_populates="calls")
    lead = relationship("Lead", back_populates="calls")

class WalletTransaction(Base):
    __tablename__ = "wallet_transactions"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    transaction_type = Column(String(50))  # credit, debit, refund
    amount = Column(Float, nullable=False)
    balance_after = Column(Float, nullable=False)
    description = Column(String(500))
    reference_id = Column(String(100))  # Razorpay order ID, call ID, etc.
    payment_method = Column(String(50))  # razorpay, upi, card, manual
    payment_details = Column(JSON)
    status = Column(String(20), default="completed")  # pending, completed, failed
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    user = relationship("User", back_populates="transactions")

class WebhookConfig(Base):
    __tablename__ = "webhook_configs"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    name = Column(String(255))
    url = Column(String(500), nullable=False)
    events = Column(JSON)  # ["call.completed", "lead.hot", "wallet.low"]
    secret = Column(String(255))
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    user = relationship("User", back_populates="webhooks")

class DLTConfig(Base):
    __tablename__ = "dlt_configs"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), unique=True, nullable=False)
    header_id = Column(String(100))
    template_id = Column(String(100))
    entity_id = Column(String(100))
    consent_template_id = Column(String(100))
    is_verified = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    user = relationship("User", back_populates="dlt_config")

class PricingPlan(Base):
    __tablename__ = "pricing_plans"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False)
    display_name = Column(String(100))
    description = Column(Text)
    price = Column(Float, nullable=False)  # INR
    credits = Column(Float, nullable=False)  # Minutes or credits
    features = Column(JSON)
    is_popular = Column(Boolean, default=False)
    is_active = Column(Boolean, default=True)
    sort_order = Column(Integer, default=0)
    created_at = Column(DateTime(timezone=True), server_default=func.now())