from __future__ import unicode_literals

import frappe
from frappe import _


def execute(filters=None):
    """Cold Storage Utilization — Query Report.

    Shows capacity_mt vs. current stock quantity (kg) for each active
    Cold Storage Unit, computed from the linked Warehouse's Bin records.
    """
    columns = [
        {"fieldname": "unit_name", "label": _("Cold Storage Unit"), "fieldtype": "Data", "width": 200},
        {"fieldname": "zone_type", "label": _("Zone Type"), "fieldtype": "Data", "width": 100},
        {"fieldname": "capacity_mt", "label": _("Capacity (MT)"), "fieldtype": "Float", "width": 120},
        {"fieldname": "capacity_kg", "label": _("Capacity (kg)"), "fieldtype": "Float", "width": 120},
        {"fieldname": "current_stock_kg", "label": _("Current Stock (kg)"), "fieldtype": "Float", "width": 130},
        {"fieldname": "current_stock_mt", "label": _("Current Stock (MT)"), "fieldtype": "Float", "precision": 2, "width": 130},
        {"fieldname": "utilization_pct", "label": _("Utilization %"), "fieldtype": "Percent", "width": 100},
        {"fieldname": "warehouse", "label": _("Warehouse"), "fieldtype": "Link", "options": "Warehouse", "width": 150},
    ]

    data = get_utilization_data(filters)
    chart = get_chart(data)

    return columns, data, None, chart


def get_utilization_data(filters=None):
    conditions = ""
    if filters:
        if filters.get("zone_type"):
            conditions += " AND csu.zone_type = %(zone_type)s"

    sql = f"""
        SELECT
            csu.unit_name,
            csu.zone_type,
            csu.capacity_mt,
            csu.capacity_mt * 1000 AS capacity_kg,
            csu.warehouse,
            COALESCE(
                (SELECT SUM(actual_qty) FROM `tabBin` WHERE warehouse = csu.warehouse),
                0
            ) AS current_stock_kg
        FROM `tabCold Storage Unit` csu
        WHERE
            csu.is_active = 1
            {conditions}
        ORDER BY csu.unit_name
    """

    data = frappe.db.sql(sql, filters or {}, as_dict=True)

    for d in data:
        d.current_stock_mt = round(d.current_stock_kg / 1000, 2) if d.current_stock_kg else 0
        if d.capacity_kg > 0:
            d.utilization_pct = round((d.current_stock_kg / d.capacity_kg) * 100, 1)
        else:
            d.utilization_pct = 0

    return data


def get_chart(data):
    """Bar chart showing utilization percentages."""
    if not data:
        return None

    labels = [d.unit_name for d in data]
    values = [d.utilization_pct for d in data]

    return {
        "data": {
            "labels": labels,
            "datasets": [
                {
                    "name": "Utilization %",
                    "values": values,
                    "chartType": "bar",
                }
            ],
        },
        "type": "bar",
        "colors": ["#3498db"],
        "barOptions": {"stacked": False},
    }
