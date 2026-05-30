# AI Expense Claim

AI-powered expense claim processing for Frappe/ERPNext. Automatically extracts expense details from receipts and bills using OpenAI.

## Demo Video



## Features

- 🤖 **AI-Powered Extraction** - Automatically extract date, amount, category, and description from bills
- 📸 **Multi-Format Support** - PDF, JPG, PNG, WEBP
- 🔄 **Batch Processing** - Upload and process multiple receipts at once
- 🎯 **Smart Grouping** - Automatically groups expenses by type and merges attachments
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
3. Select model (default: gpt-4o)

### Usage

1. Open an **Expense Claim**
2. Click  → **Upload & Process AI Based Bills**
3. Upload receipts (drag & drop or click)
4. Click **Process with AI**
5. Review and apply extracted expenses

## How It Works

1. **Upload** - Drop receipt images or PDFs
2. **Process** - AI extracts expense details in parallel
3. **Group** - Same expense types are automatically grouped
4. **Merge** - Multiple receipts merged into single PDF per group
5. **Review** - Check and edit before applying to expense claim
6. **Apply** - Selected expenses added to your claim

## Supported Categories

Food • Travel • Accommodation • Fuel • Medical • Communication • Other

## Requirements

- Frappe >= v15
- ERPNext/HRMS (for Expense Claim DocType)
- OpenAI API key

## Technical Stack

**Backend:** Python, OpenAI API, pypdf, Pillow  
**Frontend:** JavaScript, Frappe UI  
**Architecture:** Multi-threaded processing, server-side grouping

## API Methods

- `prepare_grouped_expenses` - Process and group bills (main method)
- `process_bills` - Extract data from individual files
- `merge_files_for_group` - Merge multiple receipts into PDF
- `link_files_to_claim` - Attach files to expense claim

## License

MIT
