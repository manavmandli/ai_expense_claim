from concurrent.futures import ThreadPoolExecutor, as_completed
import frappe
import io
import os
from frappe import _
from frappe.utils import flt, today,cint
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
	get_ai_expense_settings,
	calculate_group_amount,
	create_individual_groups,
	merge_payment_proof_groups,
	consolidate_same_type_groups
)

@frappe.whitelist()
def process_bills(files, settings=None):

	files = frappe.parse_json(files)
	if not files:
		frappe.throw(_("No files provided."))

	if not settings:
		settings = get_ai_expense_settings()

	client = get_openai_client(settings)
	model = settings.openai_model or "gpt-4o"
	token = settings.max_token or 300
	expense_types = frappe.get_all("Expense Claim Type", pluck="name")
	
	results = []
	low_confidence_files = []
	with ThreadPoolExecutor(max_workers=5) as executor:
		future_to_file = {}
		
		for idx, f in enumerate(files):
			mime = f.get("type", "")
			if mime.startswith("image/"):
				future = executor.submit(extract_from_image, client, model, token, f.get("data", ""), expense_types)
			else:
				future = executor.submit(extract_from_pdf, client, model, token, decode_file(f), expense_types)
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
			
			if confidence < (settings.min_confidence_for_bills or 85):
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
					is_private=cint(settings.upload_ai_processed_bills_as_private_files) or 0,
				)
				
				results.append({
					"expense_date": info.get("date") or today(),
					"expense_type": matched_type,
					"amount": flt(info.get("amount"), 2),
					"description": (info.get("description") or "")[:140],
					"file_doc_name": file_doc.name,
					"confidence": confidence,
					"document_type": info.get("document_type", "receipt"),  # bill, upi, payment, receipt
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
	settings = get_ai_expense_settings()
	response = process_bills(files, settings)

	results = response.get("results", [])
	low_confidence_files = response.get("low_confidence_files", [])

	if not results:
		return {
			"groups": [],
			"low_confidence_files": low_confidence_files
		}

	results.sort(
		key=lambda x: flt(x.get("confidence", 0)),
		reverse=True
	)

	tolerance = 0
	if cint(settings.merge_payment_proofs_with_bills):

		tolerance = flt(
			settings.duplicate_detection_amount_tolerance
		)

	# Case 1: Always create isolated groups
	grouped_items = create_individual_groups(results)

	# Case 2: Merge payment proofs
	if cint(settings.merge_payment_proofs_with_bills):
		grouped_items = merge_payment_proof_groups(
			grouped_items,
			tolerance
		)

	# Case 3: Consolidate same date + type
	if cint(settings.group_same_date_same_type_expenses):
		grouped_items = consolidate_same_type_groups(
			grouped_items
		)

	groups = build_final_groups(
		grouped_items,
		settings,
		tolerance
	)

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
def merge_files_for_group(file_doc_names, is_private=0):
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
		is_private=is_private,
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

def build_final_groups(grouped_items, settings, tolerance):
	groups = []
	for g in grouped_items:
		avg_confidence = (
			sum(g["confidences"]) / len(g["confidences"])
			if g["confidences"]
			else 95.0
		)

		final_amount = calculate_group_amount(
			g["items"],
			tolerance
		)

		attachment_url = ""
		if g["file_doc_names"]:
			try:
				is_private = cint(
					settings.upload_ai_processed_bills_as_private_files
				) or 0

				attachment_url = merge_files_for_group(
					g["file_doc_names"],
					is_private
				) or ""
				
			except Exception:
				frappe.log_error(
					title="Group Attachment Merge Error",
					message=frappe.get_traceback()
				)

		groups.append({
			"expense_type": g["expense_type"],
			"expense_date": g["expense_date"],
			"avg_confidence": round(avg_confidence, 1),
			"amount": flt(final_amount, 2),
			"description": "; ".join(g["descriptions"])[:140],
			"attachment_url": attachment_url,
			"file_doc_names": g["file_doc_names"]
		})

	groups.sort(
		key=lambda x: (
			x["expense_date"] or "9999-12-31",
			x["expense_type"] or ""
		)
	)

	return groups

