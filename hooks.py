from __future__ import unicode_literals
from frappe import _

app_name = "agri_coldchain"
app_title = "Agri Cold Chain"
app_publisher = "Your Organisation"
app_description = "Agri-Processing / Cold Chain MSME Traceability for ERPNext v15"
app_email = "info@example.com"
app_license = "MIT"

# ---------------------------------------
# DocType Class Overrides & Imports
# ---------------------------------------
doctype_js = {}
doctype_list_js = {}
doctype_tree_js = {}
doctype_treenodes = {}

# ---------------------------------------
# Fixtures — Custom Fields, Workspace, Print Format
# ---------------------------------------
fixtures = [
    {"dt": "Custom Field", "filters": [
        ["module", "=", "Agri Cold Chain"]
    ]},
    {"dt": "Workspace", "filters": [
        ["name", "=", "Cold Chain Operations"]
    ]},
    {"dt": "Print Format", "filters": [
        ["name", "=", "HACCP FSSAI Batch Certificate"]
    ]},
]

# ---------------------------------------
# DocType Permissions - standard ERPNext doctypes
# ---------------------------------------
# These are applied via Customize Form in practice, but defined here for reference
permission_query_conditions = {
    "Purchase Receipt": "agri_coldchain.permissions.get_purchase_receipt_query_conditions",
    "Quality Inspection": "agri_coldchain.permissions.get_quality_inspection_query_conditions",
}

has_permission = {
    "Purchase Receipt": "agri_coldchain.permissions.has_permission",
    "Quality Inspection": "agri_coldchain.permissions.has_permission",
}

# ---------------------------------------
# Scheduled Tasks
# ---------------------------------------
scheduler_events = {
    "daily": [
        "agri_coldchain.tasks.sync_mandi_prices"
    ],
    "daily_long": [
        "agri_coldchain.tasks.check_spoilage_risk_notifications",
        "agri_coldchain.tasks.check_cold_storage_capacity_alerts",
    ],
}

# ---------------------------------------
# Document Event Hooks
# ---------------------------------------
doc_events = {
    "Delivery Note": {
        "validate": "agri_coldchain.event_handlers.delivery_note.validate_fefo",
        "on_submit": "agri_coldchain.event_handlers.delivery_note.on_submit_fefo_override_check",
    },
    "Purchase Receipt": {
        "before_submit": "agri_coldchain.event_handlers.purchase_receipt.push_quality_data_to_batch",
    },
    "Quality Inspection": {
        "on_save": "agri_coldchain.event_handlers.quality_inspection.on_save_quality_check",
        "validate": "agri_coldchain.event_handlers.quality_inspection.compute_adjusted_shelf_life",
    },
    "Delivery Transit Log": {
        "validate": "agri_coldchain.event_handlers.delivery_transit_log.check_temperature_breach",
        "on_save": "agri_coldchain.event_handlers.delivery_transit_log.on_save_breach_notification",
    },
    "Serial and Batch Bundle": {
        "after_insert": "agri_coldchain.event_handlers.batch_bundle.set_batch_metadata_from_qi",
    },
}

# ---------------------------------------
# Website / Portal
# ---------------------------------------
website_context = {
    "favicon": "/assets/agri_coldchain/images/favicon.ico",
    "splash_image": "/assets/agri_coldchain/images/splash.png",
}

portal_menu_items = [
    {"title": "My Purchase Receipts", "route": "/purchase-receipts", "role": "Supplier"},
    {"title": "My Quality Inspections", "route": "/quality-inspections", "role": "Supplier"},
]

# ---------------------------------------
# Boot Session
# ---------------------------------------
boot_session = "agri_coldchain.boot.set_boot_session"

# ---------------------------------------
# App Include JS/CSS
# ---------------------------------------
app_include_js = []
app_include_css = []

# ---------------------------------------
# Webhook definitions (for external integrations)
# ---------------------------------------
webhooks = {
    "Farmer Settlement Notice": {
        "event": "on_submit",
        "reference_document": "Purchase Receipt",
        "is_active": 1,
        "webhook_trigger_on": "After Save",
        "webhook_doctype": "Purchase Receipt",
        "webhook_doctype_event": "on_submit",
        "request_url": "",  # Configure via API key for WhatsApp/SMS provider
        "request_method": "POST",
        "request_structure": "Form URL-Encoded",
        "webhook_json": {},
        "enable_security": 0,
    }
}
