from __future__ import unicode_literals

import frappe
from frappe import _
from frappe.utils import nowdate, get_datetime, add_days


# =============================================================================
# Delivery Note Event Handlers
# =============================================================================

def validate_fefo(doc, method):
    """FEFO Enforcement: validate that the picked batch is the oldest available.

    For each item in the Delivery Note that has batch tracking enabled,
    check whether the selected batch bundle contains the batch with the
    earliest manufacturing_date currently in stock for that item + warehouse.

    If a fresher batch is selected while an older one exists, warn or block
    depending on the user's role.
    """
    if doc.get("is_return"):
        return

    for item in doc.items:
        if not item.get("batch_no") and not item.get("serial_and_batch_bundle"):
            continue

        # Get the selected batch bundle
        batch_bundle_id = item.get("serial_and_batch_bundle")
        if not batch_bundle_id:
            continue

        bundle = frappe.get_doc("Serial and Batch Bundle", batch_bundle_id)

        for entry in bundle.entries:
            if not entry.batch_no:
                continue

            batch = frappe.get_doc("Batch", entry.batch_no)
            if not batch.manufacturing_date:
                continue

            # Find the oldest batch (earliest manufacturing_date) for this item + warehouse
            oldest_batch = _get_oldest_batch(item.item_code, bundle.warehouse)
            if not oldest_batch:
                continue

            # If the selected batch is not the oldest available, flag violation
            if oldest_batch.batch_no != entry.batch_no:
                _handle_fefo_violation(doc, item, batch, oldest_batch)


def _get_oldest_batch(item_code, warehouse):
    """Find the batch with the earliest manufacturing_date for the given item+warehouse."""
    sql = """
        SELECT
            b.name AS batch_no,
            b.manufacturing_date,
            b.expiry_date,
            sbb.name AS batch_bundle_id,
            SUM(ss.batch_qty) AS available_qty
        FROM `tabSerial and Batch Bundle` sbb
        INNER JOIN `tabSerial and Batch Entry` ss ON ss.parent = sbb.name
        INNER JOIN `tabBatch` b ON b.name = ss.batch_no
        WHERE
            sbb.item_code = %(item_code)s
            AND sbb.warehouse = %(warehouse)s
            AND sbb.docstatus = 1
            AND (b.expiry_date IS NULL OR b.expiry_date >= CURDATE())
        GROUP BY b.name, b.manufacturing_date, b.expiry_date, sbb.name
        HAVING SUM(ss.batch_qty) > 0
        ORDER BY b.manufacturing_date ASC
        LIMIT 1
    """
    result = frappe.db.sql(sql, {"item_code": item_code, "warehouse": warehouse}, as_dict=True)
    if result:
        return frappe._dict(result[0])
    return None


def _handle_fefo_violation(doc, item, selected_batch, oldest_batch):
    """Handle FEFO violation based on user role."""
    user_roles = frappe.get_roles()

    if "Cold Storage Manager" in user_roles:
        # Soft warning for managers — they have override authority
        frappe.msgprint(
            _(
                "⚠️ FEFO Warning for Item {0}:\n"
                "You selected Batch {1} (MFG: {2}), but Batch {3} (MFG: {4}) "
                "is older and available in stock.\n"
                "You have override authority as Cold Storage Manager."
            ).format(
                item.item_code,
                selected_batch.name,
                selected_batch.manufacturing_date,
                oldest_batch.batch_no,
                oldest_batch.manufacturing_date,
            ),
            title=_("FEFO Validation Warning"),
            alert=True,
            indicator="orange",
        )
        # Log the override
        _log_fefo_override(doc.name, item.item_code, selected_batch.name, oldest_batch.batch_no)
    else:
        # Block for all other roles (Warehouse Operators, etc.)
        frappe.throw(
            _(
                "⛔ FEFO Violation for Item {0}:\n"
                "You selected Batch {1} (MFG: {2}), but Batch {3} (MFG: {4}) "
                "is older and available in the same warehouse.\n\n"
                "Please pick the older batch first (First Expiry, First Out policy).\n"
                "Contact your Cold Storage Manager if you need to override this."
            ).format(
                item.item_code,
                selected_batch.name,
                selected_batch.manufacturing_date,
                oldest_batch.batch_no,
                oldest_batch.manufacturing_date,
            ),
            title=_("FEFO Violation"),
        )


def _log_fefo_override(delivery_note, item_code, selected_batch, oldest_batch):
    """Log a FEFO override for audit trail."""
    log = frappe.get_doc({
        "doctype": "Notification Log",
        "subject": _("FEFO Override — Delivery Note {0}").format(delivery_note),
        "email_content": _(
            "FEFO Override Log:\n"
            "Delivery Note: {0}\n"
            "Item: {1}\n"
            "Selected Batch: {2}\n"
            "Oldest Available Batch: {3}\n"
            "Overridden By: {4}\n"
            "Timestamp: {5}"
        ).format(
            delivery_note,
            item_code,
            selected_batch,
            oldest_batch,
            frappe.session.user,
            nowdate(),
        ),
        "document_type": "Delivery Note",
        "document_name": delivery_note,
        "for_user": "Administrator",
    })
    log.insert(ignore_permissions=True)


def on_submit_fefo_override_check(doc, method):
    """On Delivery Note submit, notify manager if FEFO overrides were logged.

    Checks the Notification Log for FEFO Override entries linked to this
    Delivery Note and sends an email summary to the Cold Storage Manager.
    """
    overrides = frappe.get_all(
        "Notification Log",
        filters={
            "document_type": "Delivery Note",
            "document_name": doc.name,
            "subject": ["like", "%FEFO Override%"],
        },
        fields=["subject", "owner", "creation"],
    )

    if not overrides:
        return

    manager_emails = frappe.db.get_all(
        "User",
        filters={"role_profile_name": "Cold Storage Manager", "enabled": 1},
        pluck="email",
    )

    if manager_emails:
        override_details = "\n".join(
            [f"- {o.subject} (by {o.owner} at {o.creation})" for o in overrides]
        )
        frappe.sendmail(
            recipients=manager_emails,
            subject=_("FEFO Override Alert — Delivery Note {0}").format(doc.name),
            message=_(
                "Delivery Note {0} was submitted with {1} FEFO override(s).\n\n"
                "Details:\n{2}\n\n"
                "Please review the FEFO Override Log for full audit trail."
            ).format(doc.name, len(overrides), override_details),
        )


# =============================================================================
# Purchase Receipt Event Handlers
# =============================================================================

def push_quality_data_to_batch(doc, method):
    """Before Purchase Receipt submission, push quality grade and shelf-life to batch metadata.

    When a Purchase Receipt with batch-tracked items is about to be submitted,
    this hook checks if a Quality Inspection was performed against the PR
    (in Draft state). If found, it pushes the grade and adjusted_shelf_life_days
    into the batch's `custom_grade` and `custom_adjusted_shelf_life_days` fields
    at the moment the Serial and Batch Bundle is created.
    """
    for item in doc.items:
        if not item.get("batch_no") and not item.get("serial_and_batch_bundle"):
            continue

        # Find the Quality Inspection linked to this Purchase Receipt
        qi = frappe.db.get_value(
            "Quality Inspection",
            {
                "reference_type": "Purchase Receipt",
                "reference_name": doc.name,
                "item_code": item.item_code,
                "docstatus": 0,  # Draft — inspection done before receipt submission
            },
            ["name", "custom_grade", "custom_adjusted_shelf_life_days"],
            as_dict=True,
        )

        if not qi:
            continue

        # Get the batch from the Serial and Batch Bundle or item's batch_no
        batch_no = item.get("batch_no")
        if not batch_no and item.get("serial_and_batch_bundle"):
            bundle = frappe.get_doc("Serial and Batch Bundle", item.serial_and_batch_bundle)
            for entry in bundle.entries:
                if entry.batch_no:
                    batch_no = entry.batch_no
                    break

        if not batch_no:
            continue

        # Push quality data into Batch record
        batch = frappe.get_doc("Batch", batch_no)
        batch.db_set("custom_grade", qi.custom_grade)
        if qi.custom_adjusted_shelf_life_days:
            batch.db_set("custom_adjusted_shelf_life_days", qi.custom_adjusted_shelf_life_days)
            new_expiry = add_days(batch.manufacturing_date, qi.custom_adjusted_shelf_life_days)
            if new_expiry:
                batch.db_set("expiry_date", new_expiry)

        frappe.msgprint(
            _("Quality data pushed to Batch {0}: Grade {1}, Shelf-life {2} days").format(
                batch_no, qi.custom_grade, qi.custom_adjusted_shelf_life_days
            ),
            alert=True,
        )





# =============================================================================
# Quality Inspection Event Handlers
# =============================================================================

def compute_adjusted_shelf_life(doc, method):
    """Compute adjusted_shelf_life_days based on quality grade.

    Grade A = 100% of base_shelf_life_days
    Grade B = 70% of base_shelf_life_days
    Grade C = 40% of base_shelf_life_days
    Grade Reject = 0
    """
    if not doc.item_code or not doc.custom_grade:
        return

    base_shelf_life = frappe.db.get_value("Item", doc.item_code, "shelf_life_in_days")
    if not base_shelf_life:
        return

    grade_multipliers = {
        "A": 1.0,
        "B": 0.7,
        "C": 0.4,
        "Reject": 0.0,
    }

    multiplier = grade_multipliers.get(doc.custom_grade, 1.0)
    doc.custom_adjusted_shelf_life_days = int(base_shelf_life * multiplier)


def on_save_quality_check(doc, method):
    """Trigger notification when Quality Inspection grade is 'Reject'."""
    if doc.custom_grade == "Reject":
        # Notify Cold Storage Manager
        manager_users = frappe.db.get_all(
            "User",
            filters={
                "role_profile_name": "Cold Storage Manager",
                "enabled": 1,
            },
            pluck="name",
        )
        for user in manager_users:
            notification = frappe.get_doc({
                "doctype": "Notification Log",
                "subject": _("Intake Quality Rejection — {0}").format(doc.name),
                "email_content": _(
                    "Quality Inspection {0} for Item {1} has been marked as REJECT.\n"
                    "Supplier: {2}\n"
                    "Reference: {3} ({4})\n\n"
                    "Action required: Review and coordinate with supplier."
                ).format(
                    doc.name,
                    doc.item_code,
                    doc.get("supplier") or "N/A",
                    doc.reference_type,
                    doc.reference_name,
                ),
                "document_type": "Quality Inspection",
                "document_name": doc.name,
                "for_user": user,
            })
            notification.insert(ignore_permissions=True)


# =============================================================================
# Delivery Transit Log Event Handlers
# =============================================================================

def check_temperature_breach(doc, method):
    """Validate and auto-set temperature_breach flag on Delivery Transit Log."""
    if not doc.arrival_temp or not doc.delivery_note:
        doc.temperature_breach = 0
        return

    # Get safe temperature threshold from the Delivery Note items
    safe_temp = _get_safe_temp_threshold(doc.delivery_note)
    if safe_temp and doc.arrival_temp > safe_temp:
        doc.temperature_breach = 1
    else:
        doc.temperature_breach = 0


def _get_safe_temp_threshold(delivery_note):
    """Get the maximum safe temperature from items in the Delivery Note."""
    dn = frappe.get_doc("Delivery Note", delivery_note)
    for item in dn.items:
        safe_temp = frappe.db.get_value("Item", item.item_code, "custom_max_safe_temp_c")
        if safe_temp:
            return safe_temp
    return None


def on_save_breach_notification(doc, method):
    """Send email notification when temperature breach is detected."""
    if not doc.temperature_breach:
        return

    # Send notification via email
    qa_emails = frappe.db.get_all(
        "User",
        filters={
            "role_profile_name": "Quality Inspector",
            "enabled": 1,
        },
        pluck="email",
    )

    # Also notify Cold Storage Manager
    cm_emails = frappe.db.get_all(
        "User",
        filters={
            "role_profile_name": "Cold Storage Manager",
            "enabled": 1,
        },
        pluck="email",
    )

    all_recipients = list(set(qa_emails + cm_emails))

    if all_recipients:
        frappe.sendmail(
            recipients=all_recipients,
            subject=_("🚨 Transit Temperature Breach — {0}").format(doc.name),
            message=_(
                "Temperature breach detected in transit!\n\n"
                "Transit Log: {0}\n"
                "Delivery Note: {1}\n"
                "Transporter: {2}\n"
                "Vehicle: {3}\n"
                "Dispatch Temp: {4}°C\n"
                "Arrival Temp: {5}°C\n\n"
                "Immediate quality assessment recommended."
            ).format(
                doc.name,
                doc.delivery_note,
                doc.transporter_name,
                doc.vehicle_no,
                doc.dispatch_temp,
                doc.arrival_temp,
            ),
        )


# =============================================================================
# Serial and Batch Bundle Event Handlers
# =============================================================================

def set_batch_metadata_from_qi(doc, method):
    """After Serial and Batch Bundle insert, set custom batch metadata from Quality Inspection.

    This handles the case where a Quality Inspection was done against a Purchase Receipt
    in Draft state, and now the batch is being created — we pull the inspection data
    and set it on the Batch record.
    """
    if not doc.entries:
        return

    # Get the first batch from the bundle
    batch_no = doc.entries[0].batch_no
    if not batch_no:
        return

    # Check if this bundle was created from a Purchase Receipt
    # The voucher_type and voucher_no fields tell us the source document
    voucher_type = doc.get("voucher_type")
    voucher_no = doc.get("voucher_no")

    if voucher_type != "Purchase Receipt" or not voucher_no:
        return

    # Find Quality Inspection for this Purchase Receipt + Item
    qi = frappe.db.get_value(
        "Quality Inspection",
        {
            "reference_type": "Purchase Receipt",
            "reference_name": voucher_no,
            "item_code": doc.item_code,
            "docstatus": 0,
        },
        ["name", "custom_grade", "custom_adjusted_shelf_life_days"],
        as_dict=True,
    )

    if not qi:
        return

    # Set metadata on Batch record
    batch = frappe.get_doc("Batch", batch_no)
    if qi.custom_grade:
        batch.db_set("custom_grade", qi.custom_grade)
    if qi.custom_adjusted_shelf_life_days:
        batch.db_set("custom_adjusted_shelf_life_days", qi.custom_adjusted_shelf_life_days)
        if batch.manufacturing_date and qi.custom_adjusted_shelf_life_days:
            new_expiry = add_days(batch.manufacturing_date, qi.custom_adjusted_shelf_life_days)
            batch.db_set("expiry_date", new_expiry)


