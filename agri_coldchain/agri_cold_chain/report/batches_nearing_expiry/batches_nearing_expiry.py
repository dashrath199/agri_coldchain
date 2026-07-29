from __future__ import unicode_literals

import frappe
from frappe import _

# Import shared logic from tasks.py to avoid duplication
from agri_coldchain.tasks import get_high_risk_batches


def execute(filters=None):
    """Batches Nearing Expiry Report — Script Report.

    Returns all active batches where risk_flag >= 0.7 (i.e., days_in_storage /
    dynamic_shelf_life > 70%). Uses shared logic from tasks.py.
    """
    columns = [
        {"fieldname": "batch_bundle_id", "label": _("Batch Bundle ID"), "fieldtype": "Link", "options": "Serial and Batch Bundle", "width": 200},
        {"fieldname": "item_code", "label": _("Item"), "fieldtype": "Link", "options": "Item", "width": 150},
        {"fieldname": "batch_no", "label": _("Batch No"), "fieldtype": "Data", "width": 150},
        {"fieldname": "warehouse", "label": _("Warehouse"), "fieldtype": "Link", "options": "Warehouse", "width": 150},
        {"fieldname": "days_in_storage", "label": _("Days in Storage"), "fieldtype": "Int", "width": 120},
        {"fieldname": "shelf_life_days", "label": _("Shelf Life (Days)"), "fieldtype": "Int", "width": 130},
        {"fieldname": "risk_pct", "label": _("Risk (%)"), "fieldtype": "Percent", "width": 100},
        {"fieldname": "qty", "label": _("Quantity"), "fieldtype": "Float", "width": 100},
        {"fieldname": "expiry_date", "label": _("Expiry Date"), "fieldtype": "Date", "width": 120},
    ]

    # Apply report-specific filtering on top of shared logic
    raw_data = get_high_risk_batches()
    data = _apply_filters(raw_data, filters)
    chart = get_chart(data)

    return columns, data, None, chart


def _apply_filters(data, filters=None):
    """Apply report-specific filters to the shared data."""
    if not filters:
        return data

    filtered = data
    if filters.get("item_code"):
        filtered = [d for d in filtered if d.get("item_code") == filters["item_code"]]
    if filters.get("warehouse"):
        filtered = [d for d in filtered if d.get("warehouse") == filters["warehouse"]]
    if filters.get("batch_no"):
        filtered = [d for d in filtered if d.get("batch_no") == filters["batch_no"]]
    if filters.get("min_risk_pct"):
        filtered = [d for d in filtered if d.get("risk_pct", 0) >= filters["min_risk_pct"]]

    return filtered


def get_chart(data):
    """Generate a bar chart for risk percentages."""
    if not data:
        return None

    labels = [d.batch_no for d in data[:20]]
    values = [d.risk_pct for d in data[:20]]

    return {
        "data": {
            "labels": labels,
            "datasets": [
                {
                    "name": "Risk %",
                    "values": values,
                    "chartType": "bar",
                }
            ],
        },
        "type": "bar",
        "colors": ["#e74c3c"],
        "barOptions": {"stacked": False},
    }
