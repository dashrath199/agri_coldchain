from __future__ import unicode_literals

import frappe
from frappe import _


def execute(filters=None):
    """Transit Breach Log — Query Report.

    Filters Delivery Transit Log records where temperature_breach = 1.
    """
    columns = [
        {"fieldname": "name", "label": _("Transit Log ID"), "fieldtype": "Link", "options": "Delivery Transit Log", "width": 180},
        {"fieldname": "delivery_note", "label": _("Delivery Note"), "fieldtype": "Link", "options": "Delivery Note", "width": 180},
        {"fieldname": "transporter_name", "label": _("Transporter"), "fieldtype": "Data", "width": 150},
        {"fieldname": "vehicle_no", "label": _("Vehicle No"), "fieldtype": "Data", "width": 120},
        {"fieldname": "dispatch_temp", "label": _("Dispatch Temp (°C)"), "fieldtype": "Float", "width": 120},
        {"fieldname": "arrival_temp", "label": _("Arrival Temp (°C)"), "fieldtype": "Float", "width": 120},
        {"fieldname": "creation", "label": _("Log Date"), "fieldtype": "Date", "width": 100},
    ]

    conditions = "WHERE dtl.temperature_breach = 1"
    if filters:
        if filters.get("from_date"):
            conditions += " AND dtl.creation >= %(from_date)s"
        if filters.get("to_date"):
            conditions += " AND dtl.creation <= %(to_date)s"
        if filters.get("transporter_name"):
            conditions += " AND dtl.transporter_name LIKE %(transporter_name)s"

    sql = f"""
        SELECT
            dtl.name,
            dtl.delivery_note,
            dtl.transporter_name,
            dtl.vehicle_no,
            dtl.dispatch_temp,
            dtl.arrival_temp,
            DATE(dtl.creation) AS creation
        FROM `tabDelivery Transit Log` dtl
        {conditions}
        ORDER BY dtl.creation DESC
    """

    data = frappe.db.sql(sql, filters or {}, as_dict=True)

    return columns, data
