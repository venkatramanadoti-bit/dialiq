import os
import base64
import json
import hmac
import hashlib
import asyncio
from typing import Dict, Any, Optional
from datetime import datetime
from dotenv import load_dotenv
import httpx

from models import User, WalletTransaction, PricingPlan
from database import get_db

load_dotenv()

PHONEPE_MERCHANT_ID = os.getenv("PHONEPE_MERCHANT_ID")
PHONEPE_SALT_KEY = os.getenv("PHONEPE_SALT_KEY")
PHONEPE_SALT_INDEX = os.getenv("PHONEPE_SALT_INDEX", "1")
PHONEPE_ENV = os.getenv("PHONEPE_ENV", "PRODUCTION")
DEMO_MODE = os.getenv("DEMO_MODE", "false").lower() == "true"

PHONEPE_BASE_URL_PRODUCTION = os.getenv("PHONEPE_BASE_URL_PRODUCTION", "https://api.phonepe.com/apis/hermes")
PHONEPE_BASE_URL_UAT = os.getenv("PHONEPE_BASE_URL_UAT", "https://api-preprod.phonepe.com/apis/hermes")

class PhonePeService:
    def __init__(self):
        self.merchant_id = PHONEPE_MERCHANT_ID
        self.salt_key = PHONEPE_SALT_KEY
        self.salt_index = PHONEPE_SALT_INDEX
        self.env = PHONEPE_ENV
        self.demo_mode = DEMO_MODE
        self.base_url = PHONEPE_BASE_URL_PRODUCTION if self.env == "PRODUCTION" else PHONEPE_BASE_URL_UAT

    def _generate_checksum(self, payload: str, endpoint: str) -> str:
        """Generate X-VERIFY checksum: base64(payload) + endpoint + SALT_KEY + '###' + SALT_INDEX"""
        string_to_hash = payload + endpoint + self.salt_key
        sha256_hash = hashlib.sha256(string_to_hash.encode()).hexdigest()
        return f"{sha256_hash}###{self.salt_index}"

    def _create_base64_payload(self, data: Dict[str, Any]) -> str:
        """Create base64 encoded payload"""
        json_str = json.dumps(data, separators=(',', ':'))
        return base64.b64encode(json_str.encode()).decode()

    async def initiate_payment(
        self,
        merchant_transaction_id: str,
        amount: float,  # in INR
        callback_url: str,
        redirect_url: str,
        user_id: int,
        plan_id: Optional[int] = None,
        mobile_number: Optional[str] = None,
        email: Optional[str] = None
    ) -> Dict[str, Any]:
        """Initiate PhonePe Standard Checkout payment"""

        amount_paise = int(amount * 100)  # Convert to paise

        payload_data = {
            "merchantId": self.merchant_id,
            "merchantTransactionId": merchant_transaction_id,
            "merchantUserId": str(user_id),
            "amount": amount_paise,
            "redirectUrl": redirect_url,
            "redirectMode": "POST",
            "callbackUrl": callback_url,
            "paymentInstrument": {
                "type": "PAY_PAGE"
            }
        }

        if mobile_number:
            payload_data["mobileNumber"] = mobile_number
        if email:
            payload_data["email"] = email

        base64_payload = self._create_base64_payload(payload_data)
        checksum = self._generate_checksum(base64_payload, "/pg/v1/pay")

        request_body = {
            "request": base64_payload
        }

        headers = {
            "Content-Type": "application/json",
            "X-VERIFY": checksum,
            "X-MERCHANT-ID": self.merchant_id
        }

        if self.demo_mode:
            # Demo mode - return mock response
            return {
                "success": True,
                "code": "PAYMENT_INITIATED",
                "message": "Demo payment initiated",
                "data": {
                    "instrumentResponse": {
                        "type": "PAY_PAGE",
                        "redirectInfo": {
                            "url": f"{redirect_url}?demo=true&merchantTransactionId={merchant_transaction_id}",
                            "method": "GET"
                        }
                    }
                }
            }

        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                f"{self.base_url}/pg/v1/pay",
                json=request_body,
                headers=headers
            )
            result = response.json()

        return result

    async def check_payment_status(self, merchant_transaction_id: str) -> Dict[str, Any]:
        """Check payment status from PhonePe"""

        endpoint = f"/pg/v1/status/{self.merchant_id}/{merchant_transaction_id}"
        checksum = self._generate_checksum("", endpoint)

        headers = {
            "Content-Type": "application/json",
            "X-VERIFY": checksum,
            "X-MERCHANT-ID": self.merchant_id
        }

        if self.demo_mode:
            return {
                "success": True,
                "code": "PAYMENT_SUCCESS",
                "message": "Demo payment successful",
                "data": {
                    "merchantTransactionId": merchant_transaction_id,
                    "transactionId": f"TXN{merchant_transaction_id}",
                    "state": "COMPLETED",
                    "responseCode": "SUCCESS",
                    "amount": 50000,  # 500 INR in paise
                    "paymentInstrument": {"type": "UPI"}
                }
            }

        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(
                f"{self.base_url}{endpoint}",
                headers=headers
            )
            result = response.json()

        return result

    def verify_callback_checksum(self, response: str, checksum_header: str) -> bool:
        """Verify checksum from PhonePe callback"""
        expected_checksum = self._generate_checksum(response, "/pg/v1/status")
        return hmac.compare_digest(expected_checksum, checksum_header)

    def process_payment_callback(self, callback_data: Dict[str, Any]) -> Dict[str, Any]:
        """Process PhonePe callback and return standardized result"""
        # PhonePe sends base64 encoded response in callback
        if "response" in callback_data:
            try:
                decoded = base64.b64decode(callback_data["response"]).decode()
                response_json = json.loads(decoded)
                return response_json
            except Exception as e:
                return {"error": f"Failed to decode callback: {str(e)}"}
        return callback_data

    async def handle_payment_success(
        self,
        db,
        user_id: int,
        merchant_transaction_id: str,
        phonepe_transaction_id: str,
        amount: float,
        plan_id: Optional[int] = None
    ) -> WalletTransaction:
        """Credit user wallet on successful payment"""
        from services.billing_service import billing_service

        plan = None
        if plan_id:
            plan = db.query(PricingPlan).filter(PricingPlan.id == plan_id).first()

        description = f"Wallet top-up via PhonePe: ₹{amount}"
        if plan:
            description += f" ({plan.display_name} Plan)"

        payment_details = {
            "phonepe_merchant_transaction_id": merchant_transaction_id,
            "phonepe_transaction_id": phonepe_transaction_id,
            "plan_id": plan_id
        }

        return billing_service.add_balance(
            db=db,
            user_id=user_id,
            amount=amount,
            description=description,
            reference_id=merchant_transaction_id,
            payment_method="phonepe",
            payment_details=payment_details
        )

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
phonepe_service = PhonePeService()