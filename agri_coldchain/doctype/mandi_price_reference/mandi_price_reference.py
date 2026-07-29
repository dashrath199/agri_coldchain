from __future__ import unicode_literals

import frappe
from frappe.model.document import Document


class MandiPriceReference(Document):
    """Mandi Price Reference — daily wholesale market prices from Agmarknet.

    Populated via a scheduled daily task (sync_mandi_prices) that fetches
    from the Government of India Agmarknet public API. Prices provide farmers
    and managers with market transparency for pricing decisions.
    """

    def validate(self):
        self.validate_prices()

    def validate_prices(self):
        if self.min_price and self.max_price and self.min_price > self.max_price:
            frappe.throw("Min Price cannot be greater than Max Price.")

        if self.modal_price:
            if self.min_price and self.modal_price < self.min_price:
                frappe.throw("Modal Price cannot be less than Min Price.")
            if self.max_price and self.modal_price > self.max_price:
                frappe.throw("Modal Price cannot be greater than Max Price.")
