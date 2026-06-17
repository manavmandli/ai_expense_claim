frappe.ui.form.on("Expense Claim", {
	custom_upload_process_aibased_bills(frm) {
		if (window.show_ai_bill_processor) {
			window.show_ai_bill_processor(frm);
		} else {
			frappe.msgprint({
				title: __("Error"),
				message: __("AI Bill Processor is not loaded. Please refresh the page."),
				indicator: "red"
			});
		}
	}
});
