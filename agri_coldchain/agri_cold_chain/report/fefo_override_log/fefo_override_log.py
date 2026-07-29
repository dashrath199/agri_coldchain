from __future__ import unicode_literals

import frappe
from frappe import _


def execute(filters=None):
    """FEFO Override Log — Query Report.

    Shows every Delivery Note where the FEFO validation was overridden,
    who overrode it, and which batch was skipped.
    """
    columns = [
        {"fieldname": "delivery_note", "label": _("Delivery Note"), "fieldtype": "Link", "options": "Delivery Note", "width": 180},
        {"fieldname": "item_code", "label": _("Item"), "fieldtype": "Link", "options": "Item", "width": 150},
        {"fieldname": "selected_batch", "label": _("Selected Batch"), "fieldtype": "Data", "width": 150},
        {"fieldname": "oldest_available_batch", "label": _("Oldest Available Batch"), "fieldtype": "Data", "width": 150},
        {"fieldname": "overridden_by", "label": _("Overridden By"), "fieldtype": "Data", "width": 150},
        {"fieldname": "override_date", "label": _("Override Date"), "fieldtype": "Date", "width": 120},
        {"fieldname": "user_role", "label": _("Role"), "fieldtype": "Data", "width": 150},
    ]

    data = get_fefo_overrides(filters)

    return columns, data


def get_fefo_overrides(filters=None):
    """Query Notification Log records that are FEFO override entries.

    Since FEFO overrides are logged as Notification Log entries with
    a specific subject pattern, we query those and parse the details.
    """
    conditions = "AND nl.subject LIKE '%FEFO Override%'"
    if filters:
        if filters.get("from_date"):
            conditions += " AND nl.creation >= %(from_date)s"
        if filters.get("to_date"):
            conditions += " AND nl.creation <= %(to_date)s"
        if filters.get("delivery_note"):
            conditions += " AND nl.document_name = %(delivery_note)s"

    sql = f"""
        SELECT
            nl.document_name AS delivery_note,
            nl.email_content AS details,
            nl.owner AS overridden_by,
            DATE(nl.creation) AS override_date
        FROM `tabNotification Log` nl
        WHERE
            nl.document_type = 'Delivery Note'
            {conditions}
        ORDER BY nl.creation DESC
    """

    raw_data = frappe.db.sql(sql, filters or {}, as_dict=True)
    parsed_data = []

    for row in raw_data:
        details = row.details or ""
        parsed_data.append({
            "delivery_note": row.delivery_note,
            "overridden_by": row.overridden_by,
            "override_date": row.override_date,
            "user_role": _get_user_role(row.overridden_by),
            # Parse item_code, selected_batch, oldest_available_batch from details
            **(_parse_details(details)),
        })

    return parsed_data


def _parse_details(details):
    """Extract item code, selected batch, and oldest batch from the notification details."""
    result = {
        "item_code": "",
        "selected_batch": "",
        "oldest_available_batch": "",
    }

    if not details:
        return result

    lines = details.split("\n")
    for line in lines:
        if "Item:" in line:
            result["item_code"] = line.split("Item:")[-1].strip()
        elif "Selected Batch:" in line:
            result["selected_batch"] = line.split("Selected Batch:")[-1].strip()
        elif "Oldest Available Batch:" in line:
            result["oldest_available_batch"] = line.split("Oldest Available Batch:")[-1].strip()

    return result


def _get_user_role(user):
    """Get the primary role of the user who performed the override."""
    roles = frappe.get_roles(user)
    # Exclude standard roles
    for role in ["Cold Storage Manager", "Quality Inspector", "Warehouse Operator"]:
        if role in roles:
            return role
    return ", ".join(roles[:3]) if roles else "Unknown"
