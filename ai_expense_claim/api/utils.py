import base64
import frappe
from frappe import _
from frappe.utils import flt

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

def calculate_group_amount(items, tolerance=0):
	if not items:
		return 0

	payment_types = {"upi", "payment"}
	bills = []
	payments = []

	for item in items:
		doc_type = (
			item.get("document_type") or "receipt"
		).lower()

		if doc_type in payment_types:
			payments.append(item)
		else:
			bills.append(item)

	total_amount = 0
	used_payments = set()

	# Add bill amounts and ignore matched payments
	for bill in bills:
		bill_amount = flt(bill.get("amount", 0))
		for idx, payment in enumerate(payments):
			if idx in used_payments:
				continue

			payment_amount = flt(payment.get("amount", 0))
			if abs(bill_amount - payment_amount) <= tolerance:
				used_payments.add(idx)
				break

		total_amount += bill_amount

	# Add unmatched payments
	for idx, payment in enumerate(payments):
		if idx in used_payments:
			continue

		total_amount += flt(payment.get("amount", 0))

	return total_amount

def create_group(item):
	desc = item.get("description", "").strip()
	confidence = flt(item.get("confidence", 0))
	file_name = item.get("file_doc_name")

	return {
		"expense_type": item.get("expense_type") or "Others",
		"expense_date": item.get("expense_date") or "",
		"items": [item],
		"descriptions": [desc] if desc else [],
		"file_doc_names": [file_name] if file_name else [],
		"confidences": [confidence] if confidence else [],
		"best_confidence": confidence
	}

def create_individual_groups(results):
	return [create_group(item) for item in results]

def merge_group_data(target, source):
    target["items"].extend(source["items"])

    target["descriptions"].extend([
        d for d in source["descriptions"]
        if d not in target["descriptions"]
    ])

    target["file_doc_names"].extend([
		
        f for f in source["file_doc_names"]
        if f not in target["file_doc_names"]
    ])

    target["confidences"].extend(source["confidences"])

    # Prefer higher confidence metadata
    if source.get("best_confidence", 0) > target.get("best_confidence", 0):
        target["best_confidence"] = source["best_confidence"]
        if source.get("expense_date"):
            target["expense_date"] = source["expense_date"]
        if source.get("expense_type"):
            target["expense_type"] = source["expense_type"]

    # if target expense_type is still "others/Others", override with source
    if (target.get("expense_type") or "others").lower() == "others" and \
       (source.get("expense_type") or "others").lower() != "others":
        target["expense_type"] = source["expense_type"]
        if source.get("expense_date"):
            target["expense_date"] = source["expense_date"]

def merge_payment_proof_groups(grouped_items, tolerance):
    payment_types = {"upi", "payment"}
    bill_types = {"bill", "receipt", "ticket"}

    # Separate into two buckets
    # "Anchor" groups: have a real expense_type (not Others) OR are a bill/receipt/ticket
    # "Orphan" groups: Others + payment/upi type → need to find a home
    anchors = []
    orphans = []

    for group in grouped_items:
        expense_type = (group.get("expense_type") or "others").lower()
        doc_types = {
            (item.get("document_type") or "receipt").lower()
            for item in group["items"]
        }
        is_payment_only = doc_types.issubset(payment_types)
        is_others = expense_type == "others"

        if is_others and is_payment_only:
            orphans.append(group)
        else:
            anchors.append(group)

    # Try to match each orphan to an anchor by date + amount within tolerance
    unmatched_orphans = []
    for orphan in orphans:
        orphan_date = orphan.get("expense_date")
        orphan_amount = flt(
            orphan["items"][0].get("amount", 0) if orphan["items"] else 0
        )

        matched = False
        for anchor in anchors:
            anchor_date = anchor.get("expense_date")
            anchor_amount = flt(
                calculate_group_amount(anchor["items"], tolerance=0)
            )

            if orphan_date != anchor_date:
                continue

            if abs(orphan_amount - anchor_amount) > tolerance:
                continue

            # Match found — merge orphan INTO anchor
            merge_group_data(anchor, orphan)
            matched = True
            break

        if not matched:
            unmatched_orphans.append(orphan)

    return anchors + unmatched_orphans

def consolidate_same_type_groups(grouped_items):
    consolidated_map = {}
    skipped = []

    for group in grouped_items:
        expense_date = group.get("expense_date") or ""
        expense_type = group.get("expense_type") or "Others"

        if not expense_date or (expense_type or "others").lower() == "others":
            skipped.append(group)
            continue

        key = (expense_date, expense_type)
        if key not in consolidated_map:
            consolidated_map[key] = group
        else:
            merge_group_data(consolidated_map[key], group)

    return list(consolidated_map.values()) + skipped
	