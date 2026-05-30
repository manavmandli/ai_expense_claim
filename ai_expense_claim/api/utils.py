import base64
import frappe
from frappe import _

def get_ai_expense_settings():
	return frappe.get_single("AI Expense Settings")

def decode_file(f):
	raw = f.get("data", "")
	if "," in raw:
		return base64.b64decode(raw.split(",", 1)[1])
	return base64.b64decode(raw)

def match_expense_type(category, expense_types):
	if not category:
		return expense_types[0] if expense_types else ""
	
	category = category.strip()
	
	# Try exact match first (case-insensitive)
	for exp_type in expense_types:
		if category.lower() == exp_type.lower():
			return exp_type
	
	# Fallback to partial match
	category_lower = category.lower()
	for exp_type in expense_types:
		if category_lower in exp_type.lower() or exp_type.lower() in category_lower:
			return exp_type
	
	# Default to first type or last type (usually "Other")
	return expense_types[-1] if expense_types else ""