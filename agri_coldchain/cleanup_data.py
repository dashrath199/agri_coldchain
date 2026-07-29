from __future__ import unicode_literals

import frappe

# Demo items — item codes starting with CC-
DEMO_ITEM_PREFIX = "CC-"

# Demo batch prefix
DEMO_BATCH_PREFIX = "DEMO-CC-"

# Customer/Supplier names created by demo_data.py
DEMO_CUSTOMERS = [
    "FreshMart Retail Chain",
    "SpiceJet Inflight Catering",
    "Star Hotel & Convention Centre",
    "GreenLeaf Exporters Ltd",
]
DEMO_SUPPLIERS = [
    "Green Valley Dairy Cooperative",
    "FreshFarm Produce Pvt Ltd",
    "Himachal Apple Growers Association",
    "Coastal Fisheries Collective",
    "Organic Mandi Farmers Trust",
]
DEMO_ITEM_GROUPS = [
    "Dairy & Milk Products", "Frozen Foods", "Fresh Fruits",
    "Fresh Vegetables", "Poultry & Meat", "Beverages & Juices",
]
DEMO_COLD_STORAGE_UNITS = [
    "Freezer Unit A1", "Chiller Unit B2", "Ambient Storage C3",
]


def execute():
    """Delete ALL demo data seeded by demo_data.py.

    Usage:
        bench --site yoursite.local execute agri_coldchain.cleanup_data.execute
    """
    print("=" * 60)
    print("  AGRI COLD CHAIN — Demo Data Cleanup")
    print("=" * 60)

    try:
        _delete_transit_logs()
        _delete_notification_logs()
        _delete_stock_entries()
        _delete_delivery_notes()
        _delete_sales_invoices()
        _delete_quality_inspections()
        _delete_sales_invoice_items()
        _delete_batches()
        _delete_mandi_prices()
        _delete_cold_storage_units()
        _delete_items()
        _delete_customers()
        _delete_suppliers()
        _delete_warehouses()
        _delete_item_groups()

        print()
        print("=" * 60)
        print("  ✅ All demo data deleted!")
        print("=" * 60)

    except Exception as e:
        frappe.db.rollback()
        print("\n  ❌ Error during cleanup: {}".format(str(e)))
        frappe.log_error(title="Agri Cold Chain Cleanup", message=str(e))
        raise


def _batch_delete(doctype, filters, label=None):
    """Delete documents matching filters in batches."""
    names = frappe.db.get_all(doctype, filters=filters, pluck="name", limit=500)
    if not names:
        return 0

    label = label or doctype
    count = len(names)
    for name in names:
        try:
            doc = frappe.get_doc(doctype, name)
            if doc.docstatus == 1:
                doc.cancel()
            doc.delete()
        except Exception as e:
            print("  ⚠️  Could not delete {} {}: {}".format(doctype, name, str(e)[:80]))

    frappe.db.commit()
    print("  🗑  Deleted {} {} record(s)".format(count, label))
    return count


def _delete_item_groups():
    """Delete demo Item Groups (except standard ones)."""
    for name in DEMO_ITEM_GROUPS:
        if frappe.db.exists("Item Group", name):
            try:
                frappe.delete_doc("Item Group", name, ignore_permissions=True)
                print("  🗑  Deleted Item Group: {}".format(name))
            except Exception as e:
                print("  ⚠️  Could not delete Item Group {}: {}".format(name, str(e)[:60]))
    frappe.db.commit()


def _delete_warehouses():
    """Delete demo Warehouses."""
    names = [
        "Cold Storage - Frozen Zone",
        "Cold Storage - Chilled Zone",
        "Cold Storage - Ambient Zone",
        "Cold Storage - Dispatch Bay",
    ]
    for wh in names:
        # Try with company abbreviation suffix
        for suffix in ["", " - CC", " - _6f"]:
            full = wh + suffix
            if frappe.db.exists("Warehouse", full):
                try:
                    frappe.delete_doc("Warehouse", full, ignore_permissions=True)
                    print("  🗑  Deleted Warehouse: {}".format(full))
                except Exception as e:
                    print("  ⚠️  Could not delete Warehouse {}: {}".format(full, str(e)[:60]))
    frappe.db.commit()


def _delete_suppliers():
    for name in DEMO_SUPPLIERS:
        if frappe.db.exists("Supplier", name):
            try:
                frappe.delete_doc("Supplier", name, ignore_permissions=True)
                print("  🗑  Deleted Supplier: {}".format(name))
            except Exception as e:
                print("  ⚠️  Could not delete Supplier {}: {}".format(name, str(e)[:60]))
    frappe.db.commit()


def _delete_customers():
    for name in DEMO_CUSTOMERS:
        if frappe.db.exists("Customer", name):
            try:
                frappe.delete_doc("Customer", name, ignore_permissions=True)
                print("  🗑  Deleted Customer: {}".format(name))
            except Exception as e:
                print("  ⚠️  Could not delete Customer {}: {}".format(name, str(e)[:60]))
    frappe.db.commit()


def _delete_items():
    """Delete demo Items (CC- prefix)."""
    names = frappe.db.get_all("Item", filters={"item_code": ["like", "CC-%"]}, pluck="name", limit=200)
    for name in names:
        if frappe.db.exists("Item", name):
            try:
                frappe.delete_doc("Item", name, ignore_permissions=True)
                print("  🗑  Deleted Item: {}".format(name))
            except Exception as e:
                print("  ⚠️  Could not delete Item {}: {}".format(name, str(e)[:60]))
    frappe.db.commit()


def _delete_cold_storage_units():
    for name in DEMO_COLD_STORAGE_UNITS:
        if frappe.db.exists("Cold Storage Unit", name):
            try:
                frappe.delete_doc("Cold Storage Unit", name, ignore_permissions=True)
                print("  🗑  Deleted Cold Storage Unit: {}".format(name))
            except Exception as e:
                print("  ⚠️  Could not delete Cold Storage Unit {}: {}".format(name, str(e)[:60]))
    frappe.db.commit()


def _delete_mandi_prices():
    _batch_delete("Mandi Price Reference", {}, "Mandi Price")


def _delete_batches():
    """Delete demo batches (DEMO-CC- prefix)."""
    names = frappe.db.get_all("Batch", filters={"batch_id": ["like", "DEMO-CC-%"]}, pluck="name", limit=200)
    for name in names:
        if frappe.db.exists("Batch", name):
            try:
                frappe.delete_doc("Batch", name, ignore_permissions=True)
                print("  🗑  Deleted Batch: {}".format(name))
            except Exception as e:
                print("  ⚠️  Could not delete Batch {}: {}".format(name, str(e)[:60]))
    frappe.db.commit()


def _delete_quality_inspections():
    """Delete demo Quality Inspections (for CC- items)."""
    names = frappe.db.get_all(
        "Quality Inspection",
        filters={"item_code": ["like", "CC-%"]},
        pluck="name", limit=200
    )
    for name in names:
        try:
            doc = frappe.get_doc("Quality Inspection", name)
            if doc.docstatus == 1:
                doc.cancel()
            frappe.delete_doc("Quality Inspection", name, ignore_permissions=True)
            print("  🗑  Deleted QI: {}".format(name))
        except Exception as e:
            print("  ⚠️  Could not delete QI {}: {}".format(name, str(e)[:60]))
    frappe.db.commit()


def _delete_sales_invoices():
    """Delete demo Sales Invoices (for demo customers)."""
    for customer in DEMO_CUSTOMERS:
        names = frappe.db.get_all(
            "Sales Invoice",
            filters={"customer": customer},
            pluck="name", limit=50
        )
        for name in names:
            try:
                doc = frappe.get_doc("Sales Invoice", name)
                if doc.docstatus == 1:
                    doc.cancel()
                frappe.delete_doc("Sales Invoice", name, ignore_permissions=True)
                print("  🗑  Deleted SI: {}".format(name))
            except Exception as e:
                print("  ⚠️  Could not delete SI {}: {}".format(name, str(e)[:60]))
    frappe.db.commit()


def _delete_sales_invoice_items():
    """Clean up any orphaned SI items (child table)."""
    # Delete SI items where parent doesn't exist
    frappe.db.sql("""
        DELETE FROM `tabSales Invoice Item`
        WHERE parent NOT IN (SELECT name FROM `tabSales Invoice`)
    """)
    frappe.db.commit()


def _delete_delivery_notes():
    """Delete demo Delivery Notes (for demo customers)."""
    for customer in DEMO_CUSTOMERS:
        names = frappe.db.get_all(
            "Delivery Note",
            filters={"customer": customer},
            pluck="name", limit=50
        )
        for name in names:
            try:
                doc = frappe.get_doc("Delivery Note", name)
                if doc.docstatus == 1:
                    doc.cancel()
                frappe.delete_doc("Delivery Note", name, ignore_permissions=True)
                print("  🗑  Deleted DN: {}".format(name))
            except Exception as e:
                print("  ⚠️  Could not delete DN {}: {}".format(name, str(e)[:60]))
    frappe.db.commit()


def _delete_stock_entries():
    """Delete demo Stock Entries (for CC- items)."""
    names = frappe.db.get_all(
        "Stock Entry",
        filters={
            "items.item_code": ["like", "CC-%"]
        } if hasattr(frappe.db, 'get_all') else {},
        pluck="name", limit=200
    ) or []
    # Fallback: get all stock entries and filter
    if not names:
        all_se = frappe.db.get_all("Stock Entry", pluck="name", limit=200)
        for name in all_se:
            items = frappe.db.get_all("Stock Entry Detail", filters={"parent": name}, fields=["item_code"], limit=1)
            if items and items[0].item_code.startswith("CC-"):
                names.append(name)
    for name in names:
        try:
            doc = frappe.get_doc("Stock Entry", name)
            if doc.docstatus == 1:
                doc.cancel()
            frappe.delete_doc("Stock Entry", name, ignore_permissions=True)
            print("  🗑  Deleted Stock Entry: {}".format(name))
        except Exception as e:
            print("  ⚠️  Could not delete Stock Entry {}: {}".format(name, str(e)[:60]))
    frappe.db.commit()


def _delete_transit_logs():
    _batch_delete("Delivery Transit Log", {}, "Transit Log")


def _delete_notification_logs():
    """Delete FEFO Override Notification Logs."""
    names = frappe.db.get_all(
        "Notification Log",
        filters={"subject": ["like", "FEFO Override%"]},
        pluck="name", limit=100
    )
    for name in names:
        try:
            frappe.delete_doc("Notification Log", name, ignore_permissions=True)
        except Exception:
            pass  # Notification Logs may have restricted delete
    if names:
        # Direct DB delete as fallback
        try:
            frappe.db.sql(
                "DELETE FROM `tabNotification Log` WHERE subject LIKE 'FEFO Override%'"
            )
        except Exception:
            pass
        print("  🗑  Deleted {} FEFO Notification Log(s)".format(len(names)))
    frappe.db.commit()
