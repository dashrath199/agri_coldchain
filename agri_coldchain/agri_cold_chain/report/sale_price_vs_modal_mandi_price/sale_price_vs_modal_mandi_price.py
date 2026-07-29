from __future__ import unicode_literals

import frappe
from frappe import _


def execute(filters=None):
    """Sale Price vs. Modal Mandi Price — Query Report.

    Compares actual sales prices against modal mandi prices for the
    same commodity/date, enabling pricing decisions based on market data.
    """
    columns = [
        {"fieldname": "sales_invoice", "label": _("Sales Invoice"), "fieldtype": "Link", "options": "Sales Invoice", "width": 180},
        {"fieldname": "posting_date", "label": _("Date"), "fieldtype": "Date", "width": 100},
        {"fieldname": "item_code", "label": _("Item"), "fieldtype": "Link", "options": "Item", "width": 150},
        {"fieldname": "item_name", "label": _("Item Name"), "fieldtype": "Data", "width": 200},
        {"fieldname": "qty", "label": _("Qty"), "fieldtype": "Float", "width": 80},
        {"fieldname": "selling_rate", "label": _("Selling Rate (₹)"), "fieldtype": "Currency", "width": 130},
        {"fieldname": "modal_mandi_price", "label": _("Modal Mandi Price (₹)"), "fieldtype": "Currency", "width": 150},
        {"fieldname": "price_difference", "label": _("Difference (₹)"), "fieldtype": "Currency", "width": 130},
        {"fieldname": "premium_pct", "label": _("Premium %"), "fieldtype": "Percent", "width": 100},
    ]

    data = get_comparison_data(filters)
    chart = get_chart(data)

    return columns, data, None, chart


def get_comparison_data(filters=None):
    conditions = ""
    if filters:
        if filters.get("from_date"):
            conditions += " AND si.posting_date >= %(from_date)s"
        if filters.get("to_date"):
            conditions += " AND si.posting_date <= %(to_date)s"
        if filters.get("item_code"):
            conditions += " AND sii.item_code = %(item_code)s"

    sql = f"""
        SELECT
            si.name AS sales_invoice,
            si.posting_date,
            sii.item_code,
            sii.item_name,
            sii.qty,
            sii.rate AS selling_rate,
            COALESCE(
                (SELECT mpr.modal_price
                 FROM `tabMandi Price Reference` mpr
                 WHERE mpr.commodity = sii.item_code
                   AND mpr.price_date <= si.posting_date
                 ORDER BY mpr.price_date DESC
                 LIMIT 1),
                0
            ) AS modal_mandi_price
        FROM `tabSales Invoice` si
        INNER JOIN `tabSales Invoice Item` sii ON sii.parent = si.name
        WHERE
            si.docstatus = 1
            {conditions}
        ORDER BY si.posting_date DESC
        LIMIT 500
    """

    data = frappe.db.sql(sql, filters or {}, as_dict=True)

    # Compute derived fields
    for d in data:
        d.price_difference = d.selling_rate - d.modal_mandi_price
        if d.modal_mandi_price > 0:
            d.premium_pct = round((d.price_difference / d.modal_mandi_price) * 100, 1)
        else:
            d.premium_pct = 0

    return data


def get_chart(data):
    """Bar chart comparing selling rate vs modal mandi price."""
    if not data:
        return None

    top_data = data[:15]
    labels = [f"{d.item_code[:15]} ({d.posting_date})" for d in top_data]

    return {
        "data": {
            "labels": labels,
            "datasets": [
                {
                    "name": "Selling Rate",
                    "values": [d.selling_rate for d in top_data],
                    "chartType": "bar",
                },
                {
                    "name": "Modal Mandi Price",
                    "values": [d.modal_mandi_price for d in top_data],
                    "chartType": "bar",
                },
            ],
        },
        "type": "bar",
        "colors": ["#1abc9c", "#3498db"],
        "barOptions": {"stacked": False},
    }
