# Copyright (c) 2026, AI Expense Claim and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from ai_expense_claim.api.expense import prepare_grouped_expenses

class AIBillTest(Document):
	pass


@frappe.whitelist()
def process_multiple_bills_test(files):
	response = prepare_grouped_expenses(files)
	
	return {
		"groups": response.get("groups", []),
		"low_confidence_files": response.get("low_confidence_files", []),
		"total_processed": len(response.get("groups", []))
	}
