# Copyright (c) 2026, Manav Mandli and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document


class AIExpenseSettings(Document):
	def validate(self):
		if self.min_confidence_for_bills < 0 or self.min_confidence_for_bills > 100:
			frappe.throw(_("Min confidence for bills must be between 0 and 100."))
