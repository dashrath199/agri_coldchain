from __future__ import unicode_literals

import frappe
from frappe.model.document import Document


class ColdStorageUnit(Document):
    """Cold Storage Unit DocType — represents a physical cold storage facility/zone.

    Each Cold Storage Unit links to a Frappe Warehouse for stock ledger consistency.
    For bin-level tracking (Facility → Chamber → Rack), nested Warehouse records
    with is_group=1 should be created deliberately during setup.
    """

    def validate(self):
        self.validate_capacity()
        self.validate_warehouse_link()

    def validate_capacity(self):
        if self.capacity_mt and self.capacity_mt <= 0:
            frappe.throw("Capacity must be greater than zero.")

    def validate_warehouse_link(self):
        if self.warehouse:
            warehouse = frappe.get_doc("Warehouse", self.warehouse)
            if warehouse.is_group:
                frappe.throw(
                    "Cannot link a Cold Storage Unit to a group Warehouse. "
                    "Select a non-group (leaf-level) warehouse."
                )

    def get_current_stock_kg(self) -> float:
        """Return the current total stock quantity (in kg) stored in the linked warehouse."""
        if not self.warehouse:
            return 0.0

        stock = frappe.db.sql(
            """
            SELECT SUM(actual_qty) as total_qty
            FROM `tabBin`
            WHERE warehouse = %s
        """,
            self.warehouse,
            as_dict=True,
        )
        return stock[0].get("total_qty") or 0.0

    def get_utilization_percent(self) -> float:
        """Calculate storage utilization as a percentage of capacity."""
        if not self.capacity_mt or self.capacity_mt <= 0:
            return 0.0

        current_stock_kg = self.get_current_stock_kg()
        capacity_kg = self.capacity_mt * 1000  # Convert MT to kg
        return min(100.0, round((current_stock_kg / capacity_kg) * 100, 2))

    def is_over_capacity(self) -> bool:
        """Check if current stock exceeds capacity."""
        if not self.capacity_mt:
            return False

        current_stock_kg = self.get_current_stock_kg()
        capacity_kg = self.capacity_mt * 1000
        return current_stock_kg > capacity_kg
