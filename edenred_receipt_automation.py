#!/usr/bin/env python3
import requests
import jwt
import json
import os
import time
import sys
from datetime import datetime, timedelta
from pathlib import Path
import csv

class EdenredBatchReceiptSubmitter:
    def __init__(self, auth_token):
        self.base_url = "https://api.edenredbenefits.com"
        self.session = requests.Session()
        self.auth_token = auth_token
        
        # Decode JWT to extract user info
        try:
            decoded = jwt.decode(auth_token, options={"verify_signature": False})
            self.member_id = int(decoded['member_id'])
            self.company_id = decoded['tpacompany_id']
            self.user_name = decoded['name']
            print(f"Authenticated as: {self.user_name} (Member ID: {self.member_id})")
        except Exception as e:
            raise Exception(f"Invalid JWT token: {e}")
        
        self.headers = {
            "Accept": "application/json",
            "Authorization": f"Bearer {auth_token}",
            "Origin": "https://myaccount.edenredbenefits.com",
            "Referer": "https://myaccount.edenredbenefits.com/",
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
        }
        
        self.expense_types = {"transit": 6, "parking": 1, "bike": 5}
        
    def upload_receipt(self, image_path):
        url = f"{self.base_url}/Claim/api/1.0/Claim/Receipt"
        
        # Detect MIME type
        ext = Path(image_path).suffix.lower()
        mime_type = {'jpg': 'image/jpeg', 'jpeg': 'image/jpeg', 'png': 'image/png', 'pdf': 'application/pdf'}.get(ext[1:], 'image/jpeg')
        
        with open(image_path, 'rb') as f:
            files = {'file': (os.path.basename(image_path), f.read(), mime_type)}
            headers = self.headers.copy()
            if 'Content-Type' in headers:
                del headers['Content-Type']
            response = self.session.post(url, files=files, headers=headers)
        
        if response.status_code == 200:
            return response.json()
        else:
            raise Exception(f"Upload failed: {response.status_code}")
    
    def extract_receipt_data(self, upload_response):
        result = upload_response.get('result', {})
        total_amount = result.get('totalAmount', {})
        merchant_data = result.get('merchantName', {})
        date_data = result.get('date', {})
        
        return {
            'amount': total_amount.get('data', 0),
            'merchant_name': merchant_data.get('data', '') if isinstance(merchant_data, dict) else str(merchant_data),
            'mongo_ref_id': result.get('mongoDbRefId', ''),
            'receipt_date': date_data.get('data', '')
        }
    
    def submit_claim(self, receipt_data, expense_date=None, merchant_override=None, expense_type="transit"):
        url = f"{self.base_url}/Claim/api/1.0/claim/claim"
        
        amount = receipt_data['amount']
        merchant_name = merchant_override or receipt_data['merchant_name'] or "Unknown"
        
        # Use receipt date for expense date if available, otherwise use provided date or today
        receipt_date = receipt_data.get('receipt_date', '')
        if expense_date:
            expense_date_str = expense_date
        elif receipt_date:
            expense_date_str = receipt_date[:10]  # Extract YYYY-MM-DD from ISO format
        else:
            expense_date_str = datetime.now().strftime("%Y-%m-%d")
        
        # Use receipt date for payment date if available, otherwise use expense date
        if receipt_date:
            payment_date = receipt_date[:10]  # Extract YYYY-MM-DD from ISO format
        else:
            payment_date = expense_date_str
        
        payload = {
            "idMember": self.member_id,
            "amount": float(amount),
            "usageDateEnd": expense_date_str,
            "usageDateStart": expense_date_str,
            "expenseDate": expense_date_str,
            "processByDate": (datetime.strptime(expense_date_str, "%Y-%m-%d") + timedelta(days=90)).strftime("%Y-%m-%d"),
            "IdBusinessAffiliation": 1,
            "idClaimType": 5,
            "idClaimReceiptType": 4,
            "idClaimStatus": 4001,
            "provider": {"name": merchant_name, "address1": "", "address2": "", "city": "", "state": "", "zip": ""},
            "claimPayment": [{"paymentDate": payment_date, "paidAmount": float(amount), "idPaymentType": 2, "idPaymentStatus": 1}],
            "claimDocuments": [{"idDocument": 0}],
            "MongoDbRefId": receipt_data['mongo_ref_id'],
            "isMultiMonthReceipt": False,
            "receiptMerchantName": merchant_name,
            "receiptPurchaseDate": receipt_date or f"{expense_date_str}T16:47:00Z",
            "receiptAmount": float(amount),
            "idSubmissionStatus": 3,
            "idExpenseType": self.expense_types.get(expense_type.lower(), 6)
        }
        
        headers = self.headers.copy()
        headers["Content-Type"] = "application/json"
        response = self.session.post(url, json=payload, headers=headers)
        
        if response.status_code == 200:
            return response.json()
        else:
            raise Exception(f"Claim failed: {response.status_code}")
    
    def process_receipt(self, image_path, expense_date=None, merchant_override=None, expense_type="transit"):
        try:
            upload_response = self.upload_receipt(image_path)
            receipt_data = self.extract_receipt_data(upload_response)
            
            print(f"✓ {image_path}: ${receipt_data['amount']} from {receipt_data['merchant_name']}")
            
            result = self.submit_claim(receipt_data, expense_date, merchant_override, expense_type)
            return {"status": "success", "receipt_data": receipt_data, "result": result}
        except Exception as e:
            print(f"✗ {image_path}: {e}")
            return {"status": "error", "error": str(e)}
    
    def batch_process(self, receipts, delay=2):
        results = []
        for i, config in enumerate(receipts, 1):
            print(f"[{i}/{len(receipts)}]", end=" ")
            result = self.process_receipt(**config)
            results.append(result)
            if i < len(receipts):
                time.sleep(delay)
        return results

def main():
    # Get auth token from command line parameter or prompt
    if len(sys.argv) > 1:
        auth_token = sys.argv[1]
        print("Using token from command line parameter")
    else:
        auth_token = input("Auth token: ").strip()
    
    try:
        submitter = EdenredBatchReceiptSubmitter(auth_token)
    except Exception as e:
        print(f"Error: {e}")
        return
    
    mode = input("Mode (1=single, 2=csv, 3=directory): ").strip()
    
    if mode == "1":
        result = submitter.process_receipt(
            image_path=input("Image path: ").strip(),
            expense_date=input("Date (YYYY-MM-DD) [auto]: ").strip() or None,
            merchant_override=input("Merchant [auto]: ").strip() or None,
            expense_type=input("Type [transit]: ").strip() or "transit"
        )
        print(result)
    
    elif mode == "2":
        csv_path = input("CSV path: ").strip()
        receipts = []
        with open(csv_path, 'r') as f:
            for row in csv.DictReader(f):
                receipts.append({
                    'image_path': row['image_path'],
                    'expense_date': row.get('expense_date'),
                    'merchant_override': row.get('merchant_name'),
                    'expense_type': row.get('expense_type', 'transit')
                })
        submitter.batch_process(receipts)
    
    elif mode == "3":
        directory = input("Directory: ").strip()
        expense_type = input("Expense type [transit]: ").strip() or "transit"
        
        receipts = []
        for ext in ["*.jpg", "*.jpeg", "*.png", "*.pdf"]:
            for file_path in Path(directory).glob(ext):
                receipts.append({
                    'image_path': str(file_path),
                    'expense_type': expense_type
                })
        
        print(f"Found {len(receipts)} files")
        if input("Continue? (y/n): ").lower() == 'y':
            submitter.batch_process(receipts)

if __name__ == "__main__":
    main()
