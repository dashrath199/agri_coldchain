from __future__ import unicode_literals
from frappe import _

def get_data():
    return {
        "doc_type": "Module",
        "module_name": "Agri Cold Chain",
        "fields": [
            {
                "label": _("Cold Storage Units"),
                "fieldtype": "Link",
                "options": "Cold Storage Unit",
            },
            {
                "label": _("Delivery Transit Log"),
                "fieldtype": "Link",
                "options": "Delivery Transit Log",
            },
            {
                "label": _("Mandi Price Reference"),
                "fieldtype": "Link",
                "options": "Mandi Price Reference",
            },
        ],
    }
