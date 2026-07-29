from __future__ import unicode_literals

import frappe
from frappe import _
from frappe.model.document import Document


class DeliveryTransitLog(Document):
    """Delivery Transit Log — records outgoing dispatch and arrival conditions.

    Tracks transporter info, dispatch/arrival temperatures, and auto-detects
    temperature breaches against the Item's configured safe threshold.
    """

    def validate(self):
        self.check_temperature_breach()

    def check_temperature_breach(self):
        """Auto-set temperature_breach flag if arrival temp exceeds safe threshold."""
        if not self.arrival_temp or not self.delivery_note:
            self.temperature_breach = 0
            return

        # Get the item's safe temperature threshold from the Delivery Note
        item_safe_temp = self._get_safe_temperature_threshold()
        if item_safe_temp and self.arrival_temp > item_safe_temp:
            self.temperature_breach = 1
        else:
            self.temperature_breach = 0

    def _get_safe_temperature_threshold(self):
        """Retrieve the maximum safe temperature from the Delivery Note items.

        Uses a custom field on Item if available; otherwise returns None.
        """
        delivery_note = frappe.get_doc("Delivery Note", self.delivery_note)
        for item in delivery_note.items:
            # Look for a custom 'max_safe_temp_c' field on Item
            safe_temp = frappe.db.get_value("Item", item.item_code, "custom_max_safe_temp_c")
            if safe_temp:
                return safe_temp
        return None

    def on_save(self):
        """Trigger notifications on temperature breach."""
        if self.temperature_breach:
            self._notify_breach()

    def _notify_breach(self):
        """Send notification to Quality Assurance Manager."""
        recipients = frappe.db.get_all(
            "User",
            filters={
                "role_profile_name": "Quality Assurance Manager",
                "enabled": 1,
            },
            pluck="email",
        )

        if recipients:
            frappe.sendmail(
                recipients=recipients,
                subject=_("Temperature Breach Detected — Delivery {0}").format(self.name),
                message=_(
                    "Temperature breach detected for Delivery Note {0}.\n"
                    "Transit Log: {1}\n"
                    "Dispatch Temp: {2}°C\n"
                    "Arrival Temp: {3}°C\n"
                    "Vehicle: {4}"
                ).format(
                    self.delivery_note,
                    self.name,
                    self.dispatch_temp,
                    self.arrival_temp,
                    self.vehicle_no,
                ),
            )
