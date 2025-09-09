# Edenred Receipt Automation

Automate receipt submission to Edenred Benefits for transit, parking, and bike expenses.

## Features

- Batch upload receipts from directory or CSV
- Automatic receipt data extraction (amount, merchant)
- Support for transit, parking, and bike expense types
- JWT token authentication
- Rate limiting to avoid API throttling

## Requirements

```bash
pip install requests PyJWT
```

## Usage

### Authentication

Get your JWT token from Edenred web app (browser dev tools → Network → Authorization header).

### Single Receipt

```bash
python edenred_receipt_automation.py [token]
# Select mode 1, enter image path and details
```

### Batch from Directory

```bash
python edenred_receipt_automation.py [token]
# Select mode 3, enter directory path
```

### Batch from CSV

```bash
python edenred_receipt_automation.py [token]
# Select mode 2, provide CSV with columns:
# image_path,expense_date,merchant_name,expense_type
```

## CSV Format

```csv
image_path,expense_date,merchant_name,expense_type
/path/to/receipt1.jpg,2024-01-15,Metro Transit,transit
/path/to/receipt2.png,2024-01-16,Parking Garage,parking
```

## Expense Types

- `transit` - Public transportation
- `parking` - Parking fees  
- `bike` - Bike-related expenses

## Notes

- Supports JPG, PNG, PDF formats
- 2-second delay between submissions
- Auto-extracts receipt data via OCR
- 90-day processing deadline applied automatically
