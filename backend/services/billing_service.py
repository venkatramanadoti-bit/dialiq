import os
import asyncio
from typing import Dict, Any, Optional, List
from datetime import datetime
from sqlalchemy.orm import Session
from dotenv import load_dotenv

from models import User, WalletTransaction, PricingPlan
from services.phonepe_service import phonepe_service

load_dotenv()

DEMO_MODE = os.getenv("DEMO_MODE", "false").lower() == "true"

class BillingService:
    def __init__(self):
        self.demo_mode = DEMO_MODE

    def get_wallet_balance(self, db: Session, user_id: int) -> float:
        """Get user's current wallet balance"""
        user = db.query(User).filter(User.id == user_id).first()
        return user.wallet_balance if user else 0.0

    def deduct_balance(self, db: Session, user_id: int, amount: float, description: str, reference_id: str = None) -> WalletTransaction:
        """Deduct amount from user's wallet"""
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            raise ValueError("User not found")

        if user.wallet_balance < amount:
            raise ValueError("Insufficient wallet balance")

        user.wallet_balance -= amount
        balance_after = user.wallet_balance

        transaction = WalletTransaction(
            user_id=user_id,
            transaction_type="debit",
            amount=amount,
            balance_after=balance_after,
            description=description,
            reference_id=reference_id,
            payment_method="wallet",
            status="completed"
        )
        db.add(transaction)
        db.commit()
        db.refresh(transaction)
        return transaction

    def add_balance(self, db: Session, user_id: int, amount: float, description: str, reference_id: str = None, payment_method: str = "phonepe", payment_details: dict = None) -> WalletTransaction:
        """Add amount to user's wallet"""
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            raise ValueError("User not found")

        user.wallet_balance += amount
        user.total_credits_purchased += amount
        balance_after = user.wallet_balance

        transaction = WalletTransaction(
            user_id=user_id,
            transaction_type="credit",
            amount=amount,
            balance_after=balance_after,
            description=description,
            reference_id=reference_id,
            payment_method=payment_method,
            payment_details=payment_details or {},
            status="completed"
        )
        db.add(transaction)
        db.commit()
        db.refresh(transaction)
        return transaction

    def get_transactions(self, db: Session, user_id: int, limit: int = 50, offset: int = 0) -> List[WalletTransaction]:
        """Get user's transaction history"""
        return db.query(WalletTransaction).filter(
            WalletTransaction.user_id == user_id
        ).order_by(WalletTransaction.created_at.desc()).offset(offset).limit(limit).all()

    def get_pricing_plans(self, db: Session) -> List[PricingPlan]:
        """Get all active pricing plans"""
        return db.query(PricingPlan).filter(PricingPlan.is_active == True).order_by(PricingPlan.sort_order).all()

    def can_make_call(self, db: Session, user_id: int, estimated_duration_minutes: float = 1) -> bool:
        """Check if user has sufficient balance for a call"""
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            return False

        per_minute_rate = float(os.getenv("PER_MINUTE_RATE", "6.0"))
        estimated_cost = estimated_duration_minutes * per_minute_rate
        return user.wallet_balance >= estimated_cost

    def get_per_minute_rate(self) -> float:
        """Get per-minute call rate"""
        return float(os.getenv("PER_MINUTE_RATE", "6.0"))

    def calculate_call_cost(self, duration_seconds: int) -> float:
        """Calculate call cost based on duration (per minute billing)"""
        per_minute_rate = self.get_per_minute_rate()
        minutes = max(1, (duration_seconds + 59) // 60)  # Round up to nearest minute
        return round(minutes * per_minute_rate, 2)

    def generate_gst_invoice(self, transaction: WalletTransaction, user: User) -> Dict[str, Any]:
        """Generate GST invoice for transaction"""
        gst_rate = 0.18  # 18% GST
        base_amount = transaction.amount / (1 + gst_rate)
        gst_amount = transaction.amount - base_amount

        return {
            "invoice_number": f"DI-{transaction.id:08d}",
            "date": transaction.created_at.strftime("%Y-%m-%d"),
            "customer": {
                "name": user.full_name or user.email,
                "email": user.email,
                "company": user.company_name,
                "gstin": getattr(user, 'gstin', None)
            },
            "items": [{
                "description": transaction.description,
                "quantity": 1,
                "unit_price": round(base_amount, 2),
                "gst_rate": 18,
                "gst_amount": round(gst_amount, 2),
                "total": round(transaction.amount, 2)
            }],
            "totals": {
                "subtotal": round(base_amount, 2),
                "cgst": round(gst_amount / 2, 2),
                "sgst": round(gst_amount / 2, 2),
                "total": round(transaction.amount, 2)
            },
            "company": {
                "name": "DialIQ Technologies Pvt Ltd",
                "address": "Bangalore, Karnataka, India",
                "gstin": "29AAACD1234A1Z5",
                "pan": "AAACD1234A"
            }
        }

# Global instance
billing_service = BillingService()