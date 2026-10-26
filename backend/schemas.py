from pydantic import BaseModel, EmailStr, Field, validator
from typing import Optional, List, Dict, Any
from datetime import datetime
from models import UserRole, CallStatus, LeadDisposition, CampaignStatus, AgentLanguage

# User Schemas
class UserBase(BaseModel):
    email: EmailStr
    full_name: Optional[str] = None
    company_name: Optional[str] = None
    phone: Optional[str] = None

class UserCreate(UserBase):
    password: str = Field(..., min_length=8)

class UserLogin(BaseModel):
    email: EmailStr
    password: str

class UserResponse(UserBase):
    id: int
    role: UserRole
    wallet_balance: float
    total_credits_purchased: float
    is_active: bool
    is_verified: bool
    created_at: datetime
    last_login: Optional[datetime]

    class Config:
        from_attributes = True

class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserResponse

# AI Agent Schemas
class ObjectionRule(BaseModel):
    trigger: str
    response: str
    action: Optional[str] = None  # transfer, end_call, continue

class KnowledgeBaseItem(BaseModel):
    question: str
    answer: str
    category: Optional[str] = None

class AIAgentBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None
    system_prompt: str
    greeting_message: Optional[str] = None
    objection_handling: List[ObjectionRule] = []
    voice_id: Optional[str] = None
    language: AgentLanguage = AgentLanguage.ENGLISH_INDIA
    speech_rate: float = Field(1.0, ge=0.5, le=2.0)
    pitch: float = Field(1.0, ge=0.5, le=2.0)
    volume: float = Field(1.0, ge=0.5, le=2.0)
    background_ambiance: bool = False
    transfer_number: Optional[str] = None
    transfer_enabled: bool = False
    knowledge_base: List[KnowledgeBaseItem] = []

class AIAgentCreate(AIAgentBase):
    pass

class AIAgentUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    system_prompt: Optional[str] = None
    greeting_message: Optional[str] = None
    objection_handling: Optional[List[ObjectionRule]] = None
    voice_id: Optional[str] = None
    language: Optional[AgentLanguage] = None
    speech_rate: Optional[float] = None
    pitch: Optional[float] = None
    volume: Optional[float] = None
    background_ambiance: Optional[bool] = None
    transfer_number: Optional[str] = None
    transfer_enabled: Optional[bool] = None
    knowledge_base: Optional[List[KnowledgeBaseItem]] = None
    is_active: Optional[bool] = None

class AIAgentResponse(AIAgentBase):
    id: int
    user_id: int
    is_active: bool
    created_at: datetime
    updated_at: Optional[datetime]

    class Config:
        from_attributes = True

# Lead Schemas
class LeadBase(BaseModel):
    name: Optional[str] = None
    phone: str
    email: Optional[EmailStr] = None
    custom_fields: Dict[str, Any] = {}

class LeadCreate(LeadBase):
    pass

class LeadBulkCreate(BaseModel):
    leads: List[LeadCreate]
    campaign_id: Optional[int] = None

class LeadUpdate(BaseModel):
    name: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[EmailStr] = None
    custom_fields: Optional[Dict[str, Any]] = None
    disposition: Optional[LeadDisposition] = None
    score: Optional[int] = None
    notes: Optional[str] = None

class LeadResponse(LeadBase):
    id: int
    user_id: int
    campaign_id: Optional[int]
    disposition: Optional[LeadDisposition]
    score: int
    notes: Optional[str]
    last_called_at: Optional[datetime]
    call_count: int
    created_at: datetime
    updated_at: Optional[datetime]

    class Config:
        from_attributes = True

# Campaign Schemas
class CampaignBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None
    agent_id: int
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    timezone: str = "Asia/Kolkata"
    concurrent_calls: int = Field(5, ge=1, le=50)
    retry_attempts: int = Field(3, ge=0, le=10)
    retry_interval: int = Field(300, ge=60, le=3600)
    retry_on: List[str] = ["busy", "no_answer"]

class CampaignCreate(CampaignBase):
    pass

class CampaignUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    agent_id: Optional[int] = None
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    timezone: Optional[str] = None
    concurrent_calls: Optional[int] = None
    retry_attempts: Optional[int] = None
    retry_interval: Optional[int] = None
    retry_on: Optional[List[str]] = None
    status: Optional[CampaignStatus] = None

class CampaignResponse(CampaignBase):
    id: int
    user_id: int
    status: CampaignStatus
    total_leads: int
    calls_made: int
    calls_answered: int
    calls_completed: int
    total_duration: int
    total_cost: float
    created_at: datetime
    updated_at: Optional[datetime]

    class Config:
        from_attributes = True

# Call Log Schemas
class TranscriptEntry(BaseModel):
    speaker: str  # "customer" or "ai"
    text: str
    timestamp: float
    confidence: Optional[float] = None

class CallLogBase(BaseModel):
    phone_number: str
    campaign_id: Optional[int] = None
    lead_id: Optional[int] = None
    agent_id: Optional[int] = None

class CallLogCreate(CallLogBase):
    pass

class CallLogResponse(CallLogBase):
    id: int
    user_id: int
    status: CallStatus
    direction: str
    duration: int
    cost: float
    transcript: List[TranscriptEntry]
    recording_url: Optional[str]
    sentiment_score: Optional[float]
    disposition: Optional[LeadDisposition]
    summary: Optional[str]
    started_at: Optional[datetime]
    answered_at: Optional[datetime]
    ended_at: Optional[datetime]
    created_at: datetime

    class Config:
        from_attributes = True

# Wallet Schemas
class WalletBalance(BaseModel):
    balance: float
    currency: str = "INR"
    per_minute_rate: float

class WalletTransactionResponse(BaseModel):
    id: int
    transaction_type: str
    amount: float
    balance_after: float
    description: str
    reference_id: Optional[str]
    payment_method: Optional[str]
    status: str
    created_at: datetime

    class Config:
        from_attributes = True

class AddCreditsRequest(BaseModel):
    amount: float = Field(..., gt=0)
    plan_id: Optional[int] = None
    payment_method: str = "razorpay"

class RazorpayOrderRequest(BaseModel):
    amount: float
    currency: str = "INR"
    receipt: Optional[str] = None

class RazorpayOrderResponse(BaseModel):
    order_id: str
    amount: int
    currency: str
    key_id: str

class RazorpayVerifyRequest(BaseModel):
    razorpay_order_id: str
    razorpay_payment_id: str
    razorpay_signature: str

# Webhook Schemas
class WebhookConfigBase(BaseModel):
    name: str
    url: str
    events: List[str]
    secret: Optional[str] = None

class WebhookConfigCreate(WebhookConfigBase):
    pass

class WebhookConfigUpdate(BaseModel):
    name: Optional[str] = None
    url: Optional[str] = None
    events: Optional[List[str]] = None
    secret: Optional[str] = None
    is_active: Optional[bool] = None

class WebhookConfigResponse(WebhookConfigBase):
    id: int
    user_id: int
    is_active: bool
    created_at: datetime
    updated_at: Optional[datetime]

    class Config:
        from_attributes = True

# DLT Config Schemas
class DLTConfigBase(BaseModel):
    header_id: Optional[str] = None
    template_id: Optional[str] = None
    entity_id: Optional[str] = None
    consent_template_id: Optional[str] = None

class DLTConfigCreate(DLTConfigBase):
    pass

class DLTConfigUpdate(DLTConfigBase):
    pass

class DLTConfigResponse(DLTConfigBase):
    id: int
    user_id: int
    is_verified: bool
    created_at: datetime
    updated_at: Optional[datetime]

    class Config:
        from_attributes = True

# Pricing Plan Schemas
class PricingPlanResponse(BaseModel):
    id: int
    name: str
    display_name: str
    description: Optional[str]
    price: float
    credits: float
    features: List[str]
    is_popular: bool
    is_active: bool

    class Config:
        from_attributes = True

# Analytics Schemas
class CallAnalytics(BaseModel):
    total_calls: int
    answered_calls: int
    completed_calls: int
    pickup_rate: float
    conversion_rate: float
    avg_duration: float
    total_duration: int
    total_cost: float
    hot_leads: int
    callbacks: int

class DailyStats(BaseModel):
    date: str
    calls: int
    answered: int
    duration: int
    cost: float
    hot_leads: int

# Demo/Simulation Schemas
class SimulateCallRequest(BaseModel):
    agent_id: int
    phone_number: str
    scenario: Optional[str] = "default"

class SimulateCallResponse(BaseModel):
    call_id: int
    transcript: List[TranscriptEntry]
    duration: int
    cost: float
    sentiment_score: float
    disposition: LeadDisposition
    summary: str
    recording_url: Optional[str]