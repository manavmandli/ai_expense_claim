from concurrent.futures import ThreadPoolExecutor, as_completed
import frappe
import io
import os
from frappe import _
from frappe.utils import flt, today
from frappe.utils.file_manager import save_file
from PIL import Image
from pypdf import PdfReader, PdfWriter
from ai_expense_claim.integration.openai import (
	get_openai_client,
	extract_from_image,
	extract_from_pdf
)
from ai_expense_claim.api.utils import (
	decode_file,
	match_expense_type,
	get_ai_expense_settings
)

@frappe.whitelist()
def process_bills(files):
	files = frappe.parse_json(files)
	if not files:
		frappe.throw(_("No files provided."))

	settings = get_ai_expense_settings()
	client = get_openai_client(settings)
	model = settings.openai_model or "gpt-4o"
	expense_types = frappe.get_all("Expense Claim Type", pluck="name")
	
	results = []
	low_confidence_files = []
	with ThreadPoolExecutor(max_workers=5) as executor:
		future_to_file = {}
		
		for idx, f in enumerate(files):
			mime = f.get("type", "")
			if mime.startswith("image/"):
				future = executor.submit(extract_from_image, client, model, f.get("data", ""), expense_types)
			else:
				future = executor.submit(extract_from_pdf, client, model, decode_file(f), expense_types)
			future_to_file[future] = (idx, f)
		
		for future in as_completed(future_to_file):
			idx, f = future_to_file[future]
			try:
				info = future.result() or {}
			except Exception:
				frappe.log_error(
					title="AI Bill Extraction Error",
					message=frappe.get_traceback()
				)
				info = {}
			
			confidence = info.get("confidence", 0)
			reason = info.get("reason", "")
			
			if confidence < (settings.min_confidence_for_bills or 86):
				low_confidence_files.append({
					"file": f.get("name", f"File {idx+1}"),
					"confidence": confidence,
					"reason": reason or "Document unreadable or not a valid bill/receipt"
				})
				continue
			
			category = (info.get("category") or "Other").strip()
			matched_type = match_expense_type(category, expense_types)
			
			try:
				content = decode_file(f)
				file_doc = save_file(
					fname=f.get("name", f"receipt_{idx+1}.pdf"),
					content=content,
					dt=None,
					dn=None,
					folder="Home",
					is_private=0,
				)
				
				results.append({
					"expense_date": info.get("date") or today(),
					"expense_type": matched_type,
					"amount": flt(info.get("amount"), 2),
					"description": (info.get("description") or "")[:140],
					"file_doc_name": file_doc.name,
					"confidence": confidence,
				})
			except Exception:
				frappe.log_error(
					title="File Save Error",
					message=frappe.get_traceback()
				)
	
	results.sort(key=lambda x: (x["expense_date"], x["expense_type"]))
	response = {
		"results": results,
		"low_confidence_files": low_confidence_files
	}
	
	return response


@frappe.whitelist()
def prepare_grouped_expenses(files):
	response = process_bills(files)
	results = response.get("results", [])
	low_confidence_files = response.get("low_confidence_files", [])
	
	if not results:
		return {
			"groups": [],
			"low_confidence_files": low_confidence_files
		}
	
	# Group by BOTH expense_date AND expense_type
	from collections import defaultdict
	group_map = defaultdict(lambda: {
		"expense_type": "",
		"expense_date": "",
		"amount": 0,
		"descriptions": [],
		"file_doc_names": [],
		"confidences": [],
		"attachment_url": ""
	})
	
	for item in results:
		item_date = item.get("expense_date") or ""
		item_type = item.get("expense_type") or ""
		key = (item_date, item_type)
		
		g = group_map[key]
		
		if not g["expense_type"]:
			g["expense_type"] = item_type
			g["expense_date"] = item_date
		
		g["amount"] += flt(item.get("amount", 0))
		
		desc = item.get("description", "").strip()
		if desc and desc not in g["descriptions"]:
			g["descriptions"].append(desc)
		
		confidence = item.get("confidence", 0)
		if confidence:
			g["confidences"].append(confidence)
		
		file_name = item.get("file_doc_name")
		if file_name:
			g["file_doc_names"].append(file_name)
	
	# Merge attachments for each group
	groups = []
	for key, g in group_map.items():
		avg_confidence = sum(g["confidences"]) / len(g["confidences"]) if g["confidences"] else 95.0
		
		if g["file_doc_names"]:
			try:
				g["attachment_url"] = merge_files_for_group(g["file_doc_names"]) or ""
			except Exception:
				frappe.log_error(
					title="Group Attachment Merge Error",
					message=frappe.get_traceback()
				)
				g["attachment_url"] = ""
		
		groups.append({
			"expense_type": g["expense_type"],
			"expense_date": g["expense_date"],
			"avg_confidence": round(avg_confidence, 1),
			"amount": flt(g["amount"], 2),
			"description": "; ".join(g["descriptions"])[:140],
			"attachment_url": g["attachment_url"],
			"file_doc_names": g["file_doc_names"]
		})
	
	# Sort by date and type (oldest date first, empty dates at the end)
	groups.sort(key=lambda x: (x["expense_date"] or "9999-12-31", x["expense_type"] or ""))
	
	return {
		"groups": groups,
		"low_confidence_files": low_confidence_files
	}


@frappe.whitelist()
def link_files_to_claim(file_doc_names, docname):
	file_doc_names = frappe.parse_json(file_doc_names)
	for name in file_doc_names:
		if name:
			try:
				frappe.db.set_value("File", name, {
					"attached_to_doctype": "Expense Claim",
					"attached_to_name": docname,
				})
			except Exception:
				frappe.log_error(
					title="File Link Error",
					message=frappe.get_traceback()
				)

@frappe.whitelist()
def merge_files_for_group(file_doc_names):
	if isinstance(file_doc_names, str):
		file_doc_names = frappe.parse_json(file_doc_names)

	if not file_doc_names:
		return None
	
	if len(file_doc_names) == 1:
		return frappe.get_value("File", file_doc_names[0], "file_url")

	writer = PdfWriter()
	for doc_name in file_doc_names:
		try:
			file_doc = frappe.get_doc("File", doc_name)
			content = file_doc.get_content()
			ext = os.path.splitext(file_doc.file_name)[1].lower()

			if ext == ".pdf":
				reader = PdfReader(io.BytesIO(content))
				for page in reader.pages:
					writer.add_page(page)
			else:
				# Convert image to PDF
				img = Image.open(io.BytesIO(content))
				if img.mode not in ("RGB", "L"):
					img = img.convert("RGB")
				img_pdf = io.BytesIO()
				img.save(img_pdf, format="PDF")
				img_pdf.seek(0)
				reader = PdfReader(img_pdf)
				for page in reader.pages:
					writer.add_page(page)
		except Exception:
			frappe.log_error(
				title="File Merge Error",
				message=frappe.get_traceback()
			)

	output = io.BytesIO()
	writer.write(output)

	merged = save_file(
		fname="merged_receipts.pdf",
		content=output.getvalue(),
		dt=None,
		dn=None,
		folder="Home",
		is_private=0,
	)
	return merged.file_url

@frappe.whitelist()
def merge_attachments_by_url(url1, url2):
	name1 = frappe.get_value("File", {"file_url": url1}, "name")
	name2 = frappe.get_value("File", {"file_url": url2}, "name")
	names = [n for n in [name1, name2] if n]

	if not names:
		return url2 or url1
	if len(names) == 1:
		return url2 if name2 else url1

	return merge_files_for_group(names)


