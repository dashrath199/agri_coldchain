from __future__ import unicode_literals

import frappe
from frappe import _


def get_purchase_receipt_query_conditions(user=None):
    """Return conditions to restrict Supplier users to their own Purchase Receipts."""
    supplier = _get_supplier_for_user(user)
    if supplier:
        return """(`tabPurchase Receipt`.supplier = {supplier})""".format(
            supplier=frappe.db.escape(supplier)
        )
    return ""


def get_quality_inspection_query_conditions(user=None):
    """Return conditions to restrict Supplier users to their own Quality Inspections."""
    supplier = _get_supplier_for_user(user)
    if supplier:
        return """(`tabQuality Inspection`.supplier = {supplier})""".format(
            supplier=frappe.db.escape(supplier)
        )
    return ""


def _get_supplier_for_user(user=None):
    """Helper to find the Supplier record linked to a portal user."""
    if not user:
        user = frappe.session.user

    if user == "Administrator":
        return None

    user_roles = frappe.get_roles(user)
    if "Supplier" not in user_roles:
        return None

    # Find the Supplier record linked to this user
    supplier = frappe.db.get_value(
        "Supplier",
        {"email_id": user},
        "name",
    )

    if not supplier:
        user_permissions = frappe.get_all(
            "User Permission",
            filters={"user": user, "allow": "Supplier"},
            pluck="for_value",
        )
        if user_permissions:
            supplier = user_permissions[0]

    return supplier


def has_permission(doc, ptype, user=None):
    """Check if a Supplier user has permission to access a specific document.

    For Supplier portal users, they can only access documents where the
    Supplier field matches their linked Supplier record.
    """
    if not user:
        user = frappe.session.user

    if user == "Administrator":
        return True

    user_roles = frappe.get_roles(user)
    if "Supplier" not in user_roles:
        return True

    # Get the supplier field value from the document
    supplier = doc.get("supplier") or doc.get("supplier_name")

    if not supplier:
        return False

    # Check if this user has a User Permission for this supplier
    has_permission = frappe.db.exists(
        "User Permission",
        {
            "user": user,
            "allow": "Supplier",
            "for_value": supplier,
        },
    )

    return bool(has_permission)
