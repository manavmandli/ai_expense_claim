import io
import json
import base64
import frappe
from frappe import _
from datetime import date
from openai import OpenAI
from pypdf import PdfReader
from pdf2image import convert_from_bytes

EXTRACT_PROMPT_TEMPLATE = """Extract expense information from this document and return ONLY valid JSON:

{{"date":"YYYY-MM-DD","category":"{categories}","amount":0,"description":"vendor+purpose","confidence":100,"reason":"","document_type":"bill|receipt|upi|payment|ticket"}}

Rules:

* Document may be in any language.
* Date: Use the value from the Date/Invoice Date/Bill Date field. Never extract a date from Bill No, Invoice No, Receipt No, Reference No, Order ID, Transaction ID, PNR, or Ticket No. For travel tickets use departure/journey date. If the document shows only a day and month with no year (e.g. "23 May"), always use {current_year} as the year.
* Amount: Use final paid/grand total only. Ignore GST, CGST, SGST, IGST, tax, service charges, and subtotals.
* Category: Must be exactly one of {categories}. Use the last category if uncertain.
* Description: Short vendor + purpose (max 60 chars).
* Document type:

  * bill = invoice/itemized bill
  * receipt = simple receipt
  * upi = UPI payment screenshot
  * payment = bank/card payment confirmation
  * ticket = travel ticket
* Confidence reflects extraction quality:

  * 90-100: amount and date clearly identified
  * 75-89: minor ambiguity
  * below 75: important information unclear
* Set reason only when confidence < 75.
* Extract best available values. Use null only when truly unreadable.
* Return JSON only.
  """

def build_prompt(expense_types):
    if not expense_types:
        expense_types = ["Other"]
    
    categories = "|".join(expense_types)
    current_year = date.today().year
    return EXTRACT_PROMPT_TEMPLATE.format(categories=categories, current_year=current_year)

def get_openai_client(settings):
	api_key = settings.get_password("openai_api_key")
	
	if not api_key:
		frappe.throw(_("OpenAI API key not configured. Please set it in AI Expense Settings."))
	
	return OpenAI(api_key=api_key)

def parse_ai_json(content):
	text = content.strip()
	if text.startswith("```"):
		lines = text.splitlines()
		if lines and lines[0].startswith("```"):
			lines = lines[1:]
		if lines and lines[-1].strip() == "```":
			lines = lines[:-1]
		text = "\n".join(lines)
	
	try:
		return json.loads(text)
	except json.JSONDecodeError:
		return None

def extract_from_image(client, model, token, data_url, expense_types=None):
	prompt = build_prompt(expense_types)
	
	try:
		response = client.chat.completions.create(
			model=model,
			messages=[{
				"role": "user",
				"content": [
					{"type": "text", "text": prompt},
					{"type": "image_url", "image_url": {"url": data_url, "detail": "high"}},
				],
			}],
			max_tokens=token,
		)
		return parse_ai_json(response.choices[0].message.content) or {}
	except Exception:
		frappe.log_error(
			title="AI Image Extraction Error",
			message=frappe.get_traceback()
		)
		return {}


def extract_from_pdf(client, model, token, data_bytes, expense_types=None):
	prompt = build_prompt(expense_types)
	try:
		reader = PdfReader(io.BytesIO(data_bytes))
		
		# Always try text extraction
		content_pages = reader.pages[:3]
		text = "\n".join(page.extract_text() or "" for page in content_pages).strip()
		
		if text and len(text) < 12000:

			full_prompt = f"{prompt}\n\nDocument text (first pages only):\n{text}"
			response = client.chat.completions.create(
				model=model,
				messages=[{"role": "user", "content": full_prompt}],
				max_tokens=token,
			)

			result = parse_ai_json(response.choices[0].message.content)
			if result and result.get("amount"):
				return result
		
		# Fall back to image mode if text extraction produced no usable result
		return extract_pdf_as_images(client, model, token, data_bytes, prompt)
		
	except Exception:
		frappe.log_error(
			title="PDF Extraction Error",
			message=frappe.get_traceback()
		)
		return {}


def extract_pdf_as_images(client, model, token, data_bytes, prompt):
	try:
		images = convert_from_bytes(data_bytes, dpi=100, fmt='jpeg')[:4]  # Max 4 pages
		
		if not images:
			return {}
		
		page_count = len(images)
		multi_page_instruction = f"""These {page_count} images are ONE document. Extract ONE expense total.
Page 1 has priority — ignore GST breakdowns, terms, and ads on later pages.

"""
		content = [{"type": "text", "text": multi_page_instruction + prompt}]
		
		for i, img in enumerate(images, 1):
			img_buffer = io.BytesIO()
			img.save(img_buffer, format='JPEG', quality=70)
			img_base64 = base64.b64encode(img_buffer.getvalue()).decode()
			data_url = f"data:image/jpeg;base64,{img_base64}"
			# First page has the actual ticket data; use high detail for it
			detail_level = "high" if i == 1 else "low"
			
			content.append({
				"type": "image_url",
				"image_url": {"url": data_url, "detail": detail_level}
			})

		response = client.chat.completions.create(
			model=model,
			messages=[{"role": "user", "content": content}],
			max_tokens=token,
		)

		return parse_ai_json(response.choices[0].message.content) or {}
	
	except Exception:
		frappe.log_error(
			title="PDF to Image Extraction Error",
			message=frappe.get_traceback()
		)
		return {}
