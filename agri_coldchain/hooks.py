# Inner hooks.py — exists so bench's is_frappe_app() passes
# The actual hooks configuration lives at the app root (../hooks.py)
# which Frappe loads at runtime.

import os

from . import __version__ as app_version

app_name = "agri_coldchain"
app_title = "Agri Cold Chain"
app_publisher = "Your Organisation"
app_description = "Agri-Processing / Cold Chain MSME Traceability for ERPNext v15"
app_email = "info@example.com"
app_license = "MIT"
