from __future__ import unicode_literals
from frappe import _

def get_data():
    return [
        {
            "module_name": "Agri Cold Chain",
            "type": "module",
            "label": _("Agri Cold Chain"),
            "color": "#1abc9c",
            "icon": "octicon octicon-squirrel",
            "description": "Cold Chain Management for Agri-Processing MSMEs",
        }
    ]
