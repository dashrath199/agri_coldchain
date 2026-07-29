from __future__ import unicode_literals

import frappe


def set_boot_session(bootinfo):
    """Set boot session data for the Agri Cold Chain app.

    Adds module-specific data to the boot session for the frontend.
    """
    bootinfo.agri_coldchain = {
        "version": "0.0.1",
        "has_mandi_price_sync": bool(
            frappe.db.count("Mandi Price Reference", {}),
        ),
        "cold_storage_units": frappe.get_all(
            "Cold Storage Unit",
            fields=["name", "unit_name", "capacity_mt", "is_active"],
        ),
        "high_risk_batches": _get_batch_dashboard_stats(),
    }


def _get_batch_dashboard_stats():
    """Get dashboard statistics for the boot session."""
    from agri_coldchain.tasks import get_high_risk_batches

    high_risk = get_high_risk_batches()
    return {
        "batches_at_risk_7_days": len(high_risk),
        "high_risk_batches": high_risk[:10],  # Return top 10 for dashboard
    }
