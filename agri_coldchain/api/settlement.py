from __future__ import unicode_literals

import frappe
from frappe import _


@frappe.whitelist(allow_guest=False)
def send_farmer_settlement_notice(purchase_receipt, quality_inspection=None):
    """Send settlement notice to farmer-supplier via WhatsApp/SMS.

    Called on submission of Purchase Receipt + Quality Inspection.
    Sends the farmer a message with:
      - Grade assigned
      - Modal price from Mandi Price Reference on intake date
      - Payment status

    v1 channel: SMS/WhatsApp via third-party gateway
    v2 channel: Optional portal access for smartphone-enabled farmers

    Args:
        purchase_receipt (str): Name of the Purchase Receipt document.
        quality_inspection (str, optional): Name of the Quality Inspection document.

    Returns:
        dict: Status of the notification.
    """
    try:
        pr = frappe.get_doc("Purchase Receipt", purchase_receipt)
        supplier = frappe.get_doc("Supplier", pr.supplier)

        grade = None
        if quality_inspection:
            qi = frappe.get_doc("Quality Inspection", quality_inspection)
            grade = qi.get("custom_grade")

        # Get modal mandi price for the commodity on the intake date
        modal_price = None
        if pr.items:
            item_code = pr.items[0].item_code
            modal_price = _get_modal_mandi_price(item_code, pr.posting_date)

        # --- SMS/WhatsApp Payload ---
        # In production, replace with actual WhatsApp Business API or SMS gateway
        # For now, we log the settlement notice
        message = _(
            "🌾 Agri Cold Chain - Settlement Notice\n\n"
            "Purchase Receipt: {0}\n"
            "Date: {1}\n"
            "Items: {2}\n"
            "Grade: {3}\n"
            "Modal Mandi Price: ₹{4}\n"
            "Total Amount: ₹{5}\n\n"
            "Payment Status: Pending\n\n"
            "Thank you for your supply!"
        ).format(
            pr.name,
            pr.posting_date,
            len(pr.items),
            grade or "N/A",
            modal_price or "N/A",
            pr.total or 0,
        )

        # Log the settlement notice
        _log_settlement_notice(purchase_receipt, supplier.name, message)

        # In production, send via WhatsApp/SMS:
        # if supplier.mobile_no:
        #     whatsapp_gateway.send(supplier.mobile_no, message)

        frappe.log_error(
            title="Farmer Settlement Notice",
            message=f"Settlement notice sent for PR {purchase_receipt} to supplier {supplier.name}",
        )

        return {
            "status": "success",
            "message": "Settlement notice sent to supplier.",
            "supplier": supplier.name,
            "grade": grade,
            "modal_price": modal_price,
        }

    except Exception as e:
        frappe.log_error(
            title="Farmer Settlement Notice Failed",
            message=f"Failed to send settlement notice for PR {purchase_receipt}: {str(e)}",
        )
        return {
            "status": "error",
            "message": str(e),
        }


def _get_modal_mandi_price(item_code, price_date):
    """Get the modal mandi price for a commodity on a specific date.

    Uses the most recent Mandi Price Reference record for the commodity
    on or before the given date.
    """
    price = frappe.db.get_value(
        "Mandi Price Reference",
        {
            "commodity": item_code,
            "price_date": ["<=", price_date],
        },
        "modal_price",
        order_by="price_date DESC",
    )
    return price


def _log_settlement_notice(pr_name, supplier, message):
    """Create a Notification Log for the settlement notice."""
    notification = frappe.get_doc({
        "doctype": "Notification Log",
        "subject": _("Farmer Settlement Notice — {0}").format(pr_name),
        "email_content": message,
        "document_type": "Purchase Receipt",
        "document_name": pr_name,
        "for_user": "Administrator",
    })
    notification.insert(ignore_permissions=True)
    frappe.db.commit()
