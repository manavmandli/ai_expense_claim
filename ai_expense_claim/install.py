import frappe
from frappe import _


def after_install():
	create_default_expense_claim_types()

def create_default_expense_claim_types():	
	default_types = [
		{
			"name": "Food",
			"expense_type": "Food",
			"description": "Expenses related to meals and food items"
		},
		{
			"name": "Travel",
			"expense_type": "Travel",
			"description": "Travel and transportation expenses"
		},
		{
			"name": "Accommodation",
			"expense_type": "Accommodation",
			"description": "Hotel and lodging expenses"
		},
		{
			"name": "Fuel",
			"expense_type": "Fuel",
			"description": "Fuel and vehicle expenses"
		},
		{
			"name": "Communication",
			"expense_type": "Communication",
			"description": "Phone, internet and communication expenses"
		}
	]
	
	for expense_type_data in default_types:
		if not frappe.db.exists("Expense Claim Type", expense_type_data["name"]):
			doc = frappe.get_doc({
				"doctype": "Expense Claim Type",
				"name": expense_type_data["name"],
				"expense_type": expense_type_data["expense_type"],
				"description": expense_type_data.get("description", "")
			})
			doc.insert(ignore_permissions=True)
	

