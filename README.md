# AI Expense Claim

AI-powered expense claim processing for Frappe/ERPNext. Automatically extracts expense details from receipts and bills using OpenAI.

## Demo Video

https://github.com/user-attachments/assets/e6fe0cf7-9f9a-45c9-836d-a50048c627b1

## Features

- 🤖 **AI-Powered Extraction** - Automatically extract date, amount, category, and description from bills
- 📸 **Multi-Format Support** - PDF, JPG, PNG, WEBP
- 🔄 **Batch Processing** - Upload and process multiple receipts at once
- 🎯 **Smart Grouping** - Optionally consolidate same-date expense types and merge payment proofs with bills
- ✅ **Quality Control** - Confidence scoring rejects low-quality images
- 🔒 **Secure** - API keys encrypted in database

## Quick Start

### Installation

```bash
bench get-app https://github.com/yourusername/ai_expense_claim
bench --site your-site install-app ai_expense_claim
```

### Configuration

1. Go to **AI Expense Settings**
2. Add your **OpenAI API Key**
3. Select the AI model (default: GPT-4o) and configure the bill processing limit.
4. Set the minimum confidence threshold.
5. Configure the duplicate detection amount tolerance.
6. Enable or disable private storage for AI processed bill uploads.
7. Enable or disable automatic grouping of same-date expense types.
8. Enable or disable merging of payment proofs (UPI/screenshots) with matching bills.

### Usage

1. Open an **Expense Claim**
2. Click  → **Upload & Process AI Based Bills**
3. Upload receipts (drag & drop or click)
4. Click **Process with AI**
5. Review and apply extracted expenses

## How It Works

1. **Upload** - Drop receipt images or PDFs
2. **Process** - AI extracts expense details in parallel
3. **Group** - Expenses can be automatically consolidated by date/type
4. **Merge** - Matching payment proofs and bills can be merged automatically
5. **Review** - Check and edit before applying to expense claim
6. **Apply** - Selected expenses added to your claim

## Supported Categories

Food • Travel • Accommodation • Fuel • Medical • Communication • Other

## Requirements

- Frappe >= v15
- ERPNext/HRMS (for Expense Claim DocType)
- OpenAI API key

## License

MIT
