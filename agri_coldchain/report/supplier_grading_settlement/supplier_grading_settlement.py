from __future__ import unicode_literals

import frappe
from frappe import _


def execute(filters=None):
    """Supplier Grading & Settlement — Query Report.

    Shows intake quality grades by supplier over time, identifying
    consistently high-quality farming partners.
    """
    columns = [
        {"fieldname": "supplier", "label": _("Supplier"), "fieldtype": "Link", "options": "Supplier", "width": 180},
        {"fieldname": "supplier_name", "label": _("Supplier Name"), "fieldtype": "Data", "width": 200},
        {"fieldname": "total_receipts", "label": _("Total Receipts"), "fieldtype": "Int", "width": 120},
        {"fieldname": "grade_a_count", "label": _("Grade A"), "fieldtype": "Int", "width": 80},
        {"fieldname": "grade_b_count", "label": _("Grade B"), "fieldtype": "Int", "width": 80},
        {"fieldname": "grade_c_count", "label": _("Grade C"), "fieldtype": "Int", "width": 80},
        {"fieldname": "reject_count", "label": _("Rejected"), "fieldtype": "Int", "width": 80},
        {"fieldname": "grade_a_pct", "label": _("Grade A %"), "fieldtype": "Percent", "width": 100},
        {"fieldname": "avg_shelf_life_days", "label": _("Avg Shelf Life (Days)"), "fieldtype": "Float", "width": 140},
        {"fieldname": "total_settlement", "label": _("Total Settlement (₹)"), "fieldtype": "Currency", "width": 150},
    ]

    data = get_supplier_grading_data(filters)

    return columns, data


def get_supplier_grading_data(filters=None):
    conditions = ""
    if filters:
        if filters.get("supplier"):
            conditions += " AND pr.supplier = %(supplier)s"
        if filters.get("from_date"):
            conditions += " AND pr.posting_date >= %(from_date)s"
        if filters.get("to_date"):
            conditions += " AND pr.posting_date <= %(to_date)s"

    sql = f"""
        SELECT
            pr.supplier,
            s.supplier_name,
            COUNT(DISTINCT pr.name) AS total_receipts,
            SUM(CASE WHEN qi.custom_grade = 'A' THEN 1 ELSE 0 END) AS grade_a_count,
            SUM(CASE WHEN qi.custom_grade = 'B' THEN 1 ELSE 0 END) AS grade_b_count,
            SUM(CASE WHEN qi.custom_grade = 'C' THEN 1 ELSE 0 END) AS grade_c_count,
            SUM(CASE WHEN qi.custom_grade = 'Reject' THEN 1 ELSE 0 END) AS reject_count,
            ROUND(AVG(qi.custom_adjusted_shelf_life_days), 1) AS avg_shelf_life_days,
            SUM(pr.total) AS total_settlement
        FROM `tabPurchase Receipt` pr
        INNER JOIN `tabSupplier` s ON s.name = pr.supplier
        LEFT JOIN `tabQuality Inspection` qi
            ON qi.reference_type = 'Purchase Receipt'
            AND qi.reference_name = pr.name
        WHERE
            pr.docstatus = 1
            {conditions}
        GROUP BY pr.supplier, s.supplier_name
        ORDER BY total_receipts DESC
    """

    data = frappe.db.sql(sql, filters or {}, as_dict=True)

    for d in data:
        if d.total_receipts > 0:
            d.grade_a_pct = round((d.grade_a_count / d.total_receipts) * 100, 1)
        else:
            d.grade_a_pct = 0

    return data
