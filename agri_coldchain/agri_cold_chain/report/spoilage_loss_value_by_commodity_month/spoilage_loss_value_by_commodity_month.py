from __future__ import unicode_literals

import frappe
from frappe import _


def execute(filters=None):
    """Spoilage Loss Value by Commodity/Month — Script Report.

    Calculates the financial value of stock that has been written off or
    expired by commodity and month, using stock valuation rates.
    """
    columns = [
        {"fieldname": "month", "label": _("Month"), "fieldtype": "Data", "width": 100},
        {"fieldname": "item_code", "label": _("Item"), "fieldtype": "Link", "options": "Item", "width": 150},
        {"fieldname": "item_name", "label": _("Item Name"), "fieldtype": "Data", "width": 200},
        {"fieldname": "spoiled_qty", "label": _("Spoiled Qty"), "fieldtype": "Float", "width": 120},
        {"fieldname": "valuation_rate", "label": _("Valuation Rate (₹)"), "fieldtype": "Currency", "width": 130},
        {"fieldname": "loss_value", "label": _("Loss Value (₹)"), "fieldtype": "Currency", "width": 130},
        {"fieldname": "stock_entry", "label": _("Stock Entry"), "fieldtype": "Link", "options": "Stock Entry", "width": 180},
    ]

    data = get_spoilage_data(filters)
    chart = get_chart(data)

    return columns, data, None, chart


def get_spoilage_data(filters=None):
    """Query stock entries where material was written off or expired."""
    conditions = ""
    if filters:
        if filters.get("from_date"):
            conditions += " AND se.posting_date >= %(from_date)s"
        if filters.get("to_date"):
            conditions += " AND se.posting_date <= %(to_date)s"
        if filters.get("item_code"):
            conditions += " AND sei.item_code = %(item_code)s"

    sql = f"""
        SELECT
            DATE_FORMAT(se.posting_date, '%%Y-%%m') AS month,
            sei.item_code,
            sei.item_name,
            ABS(sei.qty) AS spoiled_qty,
            sei.valuation_rate,
            ROUND(ABS(sei.qty) * sei.valuation_rate, 2) AS loss_value,
            se.name AS stock_entry
        FROM `tabStock Entry` se
        INNER JOIN `tabStock Entry Detail` sei ON sei.parent = se.name
        WHERE
            se.stock_entry_type IN ('Material Issue', 'Material Transfer', 'Manufacture')
            AND sei.qty < 0
            AND se.docstatus = 1
            {conditions}
        ORDER BY se.posting_date DESC
    """

    return frappe.db.sql(sql, filters or {}, as_dict=True)


def get_chart(data):
    """Generate a bar chart of spoilage loss by month."""
    if not data:
        return None

    from collections import defaultdict
    monthly_loss = defaultdict(float)
    for d in data:
        monthly_loss[d.month] += d.loss_value

    months = sorted(monthly_loss.keys())
    values = [monthly_loss[m] for m in months]

    return {
        "data": {
            "labels": months,
            "datasets": [
                {
                    "name": "Spoilage Loss (₹)",
                    "values": values,
                    "chartType": "bar",
                }
            ],
        },
        "type": "bar",
        "colors": ["#e74c3c"],
        "barOptions": {"stacked": False},
    }
