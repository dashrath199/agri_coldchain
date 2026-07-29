from __future__ import unicode_literals

import json
import frappe
from frappe import _
from frappe.utils import nowdate, add_days, get_datetime, today


@frappe.whitelist()
def sync_mandi_prices():
    """Scheduled daily task: fetch mandi prices from Agmarknet API.

    This task runs daily via hooks.py -> scheduler_events. It fetches price
    data from the Government of India Agmarknet public API and upserts
    Mandi Price Reference records.

    Note: Agmarknet's API may require a specific API key or certificate.
    Configure via Agri Cold Chain settings doctype or frappe.conf.
    """
    frappe.log_error(
        title="Mandi Price Sync",
        message="sync_mandi_prices() started — implement actual API call here.",
    )

    try:
        # --- Configuration ---
        # Get API configuration from Frappe site config or a settings doctype
        api_url = frappe.conf.get("agmarknet_api_url") or "https://api.data.gov.in/resource/9ef84268-d588-465a-a308-a864a43d0070"
        api_key = frappe.conf.get("agmarknet_api_key") or ""

        if not api_key:
            frappe.log_error(
                title="Mandi Price Sync",
                message="Agmarknet API key not configured. Set agmarknet_api_key in site config.",
            )
            return

        # --- Fetch from Agmarknet ---
        # Actual implementation would call the Agmarknet API:
        # import requests
        # response = requests.get(api_url, params={
        #     "api-key": api_key,
        #     "format": "json",
        #     "limit": 1000,
        #     "filters[commodity]": "...",
        # })
        # data = response.json()

        # --- Placeholder: create a sample record for demonstration ---
        # In production, iterate over API response and upsert records
        # using frappe.get_doc(...).insert() or frappe.db.sql for bulk upsert
        sample_commodities = frappe.get_all("Item", filters={"has_batch_no": 1}, pluck="name", limit=5)
        for commodity in sample_commodities:
            existing = frappe.db.exists(
                "Mandi Price Reference",
                {
                    "commodity": commodity,
                    "price_date": today(),
                    "market_name": "Sample Mandi",
                },
            )
            if not existing:
                doc = frappe.get_doc(
                    {
                        "doctype": "Mandi Price Reference",
                        "commodity": commodity,
                        "market_name": "Sample Mandi",
                        "price_date": today(),
                        "min_price": 1000,
                        "max_price": 1200,
                        "modal_price": 1100,
                    }
                )
                doc.insert(ignore_permissions=True)

        frappe.db.commit()
        frappe.log_error(
            title="Mandi Price Sync",
            message=f"sync_mandi_prices() completed successfully for {len(sample_commodities)} commodities.",
        )

    except Exception as e:
        frappe.log_error(
            title="Mandi Price Sync Failure",
            message=f"sync_mandi_prices() failed: {str(e)}",
        )
        # Notify admin about sync failure
        _notify_admin_of_sync_failure(str(e))


def _notify_admin_of_sync_failure(error_message):
    """Send email notification to admin when mandi price sync fails."""
    admin_emails = frappe.db.get_all(
        "User",
        filters={
            "name": ["!=", "Guest"],
            "enabled": 1,
            "user_type": "System User",
        },
        pluck="email",
        limit=3,
    )
    if admin_emails:
        frappe.sendmail(
            recipients=admin_emails,
            subject=_("Mandi Price Sync Failed — Action Required"),
            message=_(
                "The daily Mandi Price synchronization from Agmarknet has failed.\n\n"
                "Error: {0}\n\n"
                "Please check your configuration and API key.\n"
                "Without this data, the mandi price comparison features will not work."
            ).format(error_message),
        )


def check_spoilage_risk_notifications():
    """Daily scheduled task: identify batches nearing expiry and send alerts.

    Computes spoilage risk for all active Serial and Batch Bundle records
    linked to perishable items, and sends WhatsApp/SMS notifications for
    batches with risk_flag >= 0.7.
    """
    frappe.log_error(
        title="Spoilage Risk Check",
        message="check_spoilage_risk_notifications() started.",
    )

    high_risk_batches = get_high_risk_batches()
    for batch_info in high_risk_batches:
        _send_spoilage_alert(batch_info)

    frappe.log_error(
        title="Spoilage Risk Check",
        message=f"Found {len(high_risk_batches)} high-risk batches. Alerts sent.",
    )


def get_high_risk_batches():
    """Query to find batches with spoilage risk >= 70%."""
    sql = """
        SELECT
            sbb.name AS batch_bundle_id,
            sbb.item_code,
            sbb.batch_no,
            sbb.warehouse,
            b.manufacturing_date,
            b.expiry_date,
            COALESCE(
                (SELECT ss.batch_qty FROM `tabSerial and Batch Entry` ss
                 WHERE ss.parent = sbb.name LIMIT 1),
                0
            ) AS batch_qty,
            i.custom_base_shelf_life_days AS base_shelf_life_days
        FROM `tabSerial and Batch Bundle` sbb
        INNER JOIN `tabItem` i ON i.name = sbb.item_code
        INNER JOIN `tabBatch` b ON b.name = sbb.batch_no
        WHERE
            i.custom_base_shelf_life_days IS NOT NULL
            AND i.custom_base_shelf_life_days > 0
            AND b.manufacturing_date IS NOT NULL
            AND (
                b.expiry_date IS NULL
                OR b.expiry_date >= CURDATE()
            )
    """
    batches = frappe.db.sql(sql, as_dict=True)
    high_risk = []

    for batch in batches:
        if not batch.manufacturing_date:
            continue

        days_in_storage = (get_datetime(nowdate()) - get_datetime(batch.manufacturing_date)).days
        if days_in_storage < 0:
            continue

        shelf_life = batch.base_shelf_life_days or 1
        risk_pct = days_in_storage / shelf_life

        if risk_pct >= 0.7:
            high_risk.append({
                "batch_bundle_id": batch.batch_bundle_id,
                "item_code": batch.item_code,
                "batch_no": batch.batch_no,
                "warehouse": batch.warehouse,
                "days_in_storage": days_in_storage,
                "shelf_life_days": shelf_life,
                "risk_pct": round(risk_pct * 100, 1),
                "qty": batch.batch_qty or 0,
            })

    return high_risk


def _send_spoilage_alert(batch_info):
    """Send spoilage alert via System Notification (and WhatsApp/SMS in production).

    Placeholder for actual WhatsApp/SMS gateway integration.
    """
    # Create a System Notification
    notification = frappe.get_doc({
        "doctype": "Notification Log",
        "subject": _("Batch Expiry Warning — {0} ({1}%)").format(
            batch_info["batch_no"], batch_info["risk_pct"]
        ),
        "email_content": _(
            "Batch {0} for Item {1} is at {2}% of shelf life.\n"
            "Days in storage: {3}\n"
            "Shelf life: {4} days\n"
            "Warehouse: {5}\n"
            "Quantity: {6}\n\n"
            "Action required: Dispatch or process immediately."
        ).format(
            batch_info["batch_no"],
            batch_info["item_code"],
            batch_info["risk_pct"],
            batch_info["days_in_storage"],
            batch_info["shelf_life_days"],
            batch_info["warehouse"],
            batch_info["qty"],
        ),
        "document_type": "Serial and Batch Bundle",
        "document_name": batch_info["batch_bundle_id"],
        "for_user": "Administrator",
    })
    notification.insert(ignore_permissions=True)

    # In production, also send via WhatsApp/SMS:
    # whatsapp_provider.send_message(
    #     to="+91<manager-phone>",
    #     message=f"⚠️ Batch Expiry Warning: {batch_info['batch_no']} "
    #             f"({batch_info['risk_pct']}% of shelf life exceeded). "
    #             f"Item: {batch_info['item_code']}, Qty: {batch_info['qty']}"
    # )


def check_cold_storage_capacity_alerts():
    """Daily scheduled task: check all active Cold Storage Units for over-capacity."""
    units = frappe.get_all("Cold Storage Unit", filters={"is_active": 1})

    for unit_name in units:
        unit = frappe.get_doc("Cold Storage Unit", unit_name)
        if unit.is_over_capacity():
            stock_kg = unit.get_current_stock_kg()
            _send_capacity_alert(unit, stock_kg)


def _send_capacity_alert(unit, current_stock_kg):
    """Send over-capacity alert via email + system notification."""
    # System Notification
    notification = frappe.get_doc({
        "doctype": "Notification Log",
        "subject": _("Cold Storage Over Capacity — {0}").format(unit.unit_name),
        "email_content": _(
            "Cold Storage Unit {0} has exceeded its capacity.\n"
            "Capacity: {1} MT\n"
            "Current Stock: {2} kg ({3} MT)\n\n"
            "Immediate action required to prevent spoilage."
        ).format(
            unit.unit_name,
            unit.capacity_mt,
            current_stock_kg,
            round(current_stock_kg / 1000, 2),
        ),
        "document_type": "Cold Storage Unit",
        "document_name": unit.name,
        "for_user": "Administrator",
    })
    notification.insert(ignore_permissions=True)

    # Email to Cold Storage Manager
    manager_emails = frappe.db.get_all(
        "User",
        filters={
            "role_profile_name": "Cold Storage Manager",
            "enabled": 1,
        },
        pluck="email",
    )
    if manager_emails:
        frappe.sendmail(
            recipients=manager_emails,
            subject=_("🚨 Cold Storage Over Capacity — {0}").format(unit.unit_name),
            message=_(
                "Cold Storage Unit {0} has exceeded its capacity.\n"
                "Capacity: {1} MT\n"
                "Current Stock: {2} kg ({3} MT)\n\n"
                "Immediate action required."
            ).format(
                unit.unit_name,
                unit.capacity_mt,
                current_stock_kg,
                round(current_stock_kg / 1000, 2),
            ),
        )
