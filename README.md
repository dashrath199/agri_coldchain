# AGRI COLD CHAIN
## Cold Chain Traceability — Temperature, FEFO & Quality-Based Shelf Life for ERPNext

**App Name:** Agri Cold Chain
**Version:** 0.0.1
**Modules:** Agri Cold Chain
**Domain:** Agri-Processing / Cold Chain (Dairy, Meat, Fruits, Vegetables, Frozen Foods)
**Required Apps:** Frappe v15, ERPNext v15 (parent bench)
**Repository:** https://github.com/dashrath199/agri_coldchain
**Last Updated:** July 31, 2026

---

## TABLE OF CONTENTS

1. [Application Overview](#1-application-overview)
2. [System Architecture](#2-system-architecture)
3. [Getting Started](#3-getting-started)
4. [Feature 1: Quality Inspection → Shelf Life Adjustment](#4-feature-1-quality-inspection--shelf-life-adjustment)
5. [Feature 2: FEFO Enforcement on Delivery Notes](#5-feature-2-fefo-enforcement-on-delivery-notes)
6. [Feature 3: Transit Temperature Breach Detection](#6-feature-3-transit-temperature-breach-detection)
7. [Feature 4: Cold Storage Capacity & Mandi Price Reference](#7-feature-4-cold-storage-capacity--mandi-price-reference)
8. [Reports](#8-reports)
9. [Workspace Navigation](#9-workspace-navigation)
10. [Notifications & Alerts](#10-notifications--alerts)
11. [Setup & Configuration (Fixtures)](#11-setup--configuration-fixtures)
12. [Demo Data](#12-demo-data)
13. [Known Limitations](#13-known-limitations)
14. [Troubleshooting](#14-troubleshooting)
15. [Appendix](#15-appendix)

---

## 1. APPLICATION OVERVIEW

### 1.1 Purpose

Agri Cold Chain is a Frappe/ERPNext v15 custom app that adds perishable-goods traceability on top of standard ERPNext inventory. It targets the specific failure modes of cold-chain logistics that a general-purpose stock system doesn't cover:

- **Temperature breaches in transit** go unrecorded, so spoiled shipments can't be traced to a transporter.
- **FIFO instead of FEFO** — stock systems ship the oldest-*received* batch, not the soonest-to-*expire* batch, so fresher stock gets shipped ahead of stock that's about to go bad.
- **A static shelf life** — ERPNext's standard `shelf_life_in_days` is the same for every batch of an item, even though a Grade-B or Grade-C batch spoils faster than a Grade-A one.

### 1.2 Key Features

- **3 custom DocTypes** — Cold Storage Unit, Delivery Transit Log, Mandi Price Reference
- **10 custom fields** — 3 on Item, 2 on Batch, 4 on Quality Inspection (Batch and QI share `custom_grade` / `custom_adjusted_shelf_life_days`)
- **1 Workspace** — Cold Chain Operations, with 22 shortcuts across 5 sections
- **7 Query/Script Reports** — expiry risk, utilization, price comparison, supplier grading, FEFO audit, breach log, spoilage loss
- **5 doc_events automations** across Delivery Note, Purchase Receipt, Quality Inspection, Delivery Transit Log, and Serial and Batch Bundle
- **3 scheduled tasks** — daily mandi price sync, daily spoilage-risk check, daily capacity check
- **1 whitelisted API method** — `send_farmer_settlement_notice` (settlement notice to a supplier after grading)
- **5 seeded Dashboard Charts + 5 Number Cards** (fixtures exist but are not yet wired into the workspace page — see [13.5](#13-known-limitations))
- **1 Print Format** — "HACCP FSSAI Batch Certificate" on Serial and Batch Bundle
- **Role-based permissions** referencing 4 roles: Cold Storage Manager, Quality Inspector, Warehouse Operator, Supplier

### 1.3 Scope Note

This app is built on ERPNext v15 to demonstrate Frappe development across DocTypes, doc_events, scheduler_events, permission hooks, Query/Script Reports, Workspaces, fixtures, and a webhook-style settlement notice. It is **not** presented as production-hardened — [Section 13](#13-known-limitations) is an honest, code-verified account of what would need to be fixed before a real deployment, including a hook-wiring bug that currently prevents the core automation from loading at all.

---

## 2. SYSTEM ARCHITECTURE

### 2.1 Technology Stack

- **Framework:** Frappe v15 / ERPNext v15
- **Database:** MariaDB
- **Automation:** Frappe `doc_events` + `scheduler_events` (daily and daily_long)
- **Dependencies:** `requests>=2.31.0` (declared in `requirements.txt`; used only by the still-placeholder mandi price sync — see [13.6](#13-known-limitations))

### 2.2 DocType Structure

| # | DocType Name | Type | Autoname | Submittable |
|---|--------------|------|----------|:-----------:|
| 1 | Cold Storage Unit | Document | `field:unit_name` | ❌ |
| 2 | Delivery Transit Log | Document | `format:TRANSIT-{#####}` | ❌ |
| 3 | Mandi Price Reference | Document | `format:MANDI-{commodity}-{#####}` | ❌ |

> **Note:** All three carry an `amended_from` field even though none are submittable — harmless, but the field only does something on doctypes with `is_submittable = 1`.

### 2.3 Data Flow Diagram

```
┌──────────────────────────────────────────────────────────────────────────┐
│                          END-TO-END WORKFLOW                             │
├──────────────────────────────────────────────────────────────────────────┤
│                                                                            │
│  🚜 INTAKE                                                                │
│  ┌──────────────┐                                                        │
│  │ Purchase      │  Item carries the "rulebook":                         │
│  │ Receipt       │  custom_base_shelf_life_days, custom_max_safe_temp_c, │
│  │ + Batch       │  custom_requires_quality_inspection                   │
│  └──────┬───────┘                                                        │
│         ▼                                                                │
│  🧪 QUALITY INSPECTION                                                    │
│  ┌──────────────────────────────────────────────────────────┐           │
│  │ compute_adjusted_shelf_life() on validate:                │           │
│  │   Grade A → 100% · B → 70% · C → 40% · Reject → 0%        │           │
│  └──────┬─────────────────────────────────────────────────────┘         │
│         ▼                                                                │
│  📦 BATCH (shelf life shortened, expiry_date recalculated)               │
│  ┌──────────────────────────────────────────────────────────┐           │
│  │ push_quality_data_to_batch (PR before_submit)              │           │
│  │ set_batch_metadata_from_qi (SBB after_insert)               │           │
│  │   → both write custom_grade + custom_adjusted_shelf_life_days│         │
│  └──────┬─────────────────────────────────────────────────────┘         │
│         ▼                                                                │
│  ❄️ STORAGE — Cold Storage Unit utilization vs capacity_mt               │
│         ▼                                                                │
│  🧾 SALES ORDER → DELIVERY NOTE                                          │
│  ┌──────────────────────────────────────────────────────────┐           │
│  │ validate_fefo(): oldest-expiring batch must be picked.     │           │
│  │  Cold Storage Manager → warning + logged override          │           │
│  │  Anyone else → blocked                                     │           │
│  └──────┬─────────────────────────────────────────────────────┘         │
│         ▼                                                                │
│  🚚 DELIVERY TRANSIT LOG                                                 │
│  ┌──────────────────────────────────────────────────────────┐           │
│  │ check_temperature_breach(): arrival_temp vs item's          │           │
│  │  custom_max_safe_temp_c → temperature_breach flag           │           │
│  └──────┬─────────────────────────────────────────────────────┘         │
│         ▼                                                                │
│  ⚠️ SPOILAGE RISK (daily scheduler) → Material Issue write-off           │
│         ▼                                                                │
│  💸 SPOILAGE LOSS REPORT — ₹ value lost, by commodity/month              │
│                                                                            │
└──────────────────────────────────────────────────────────────────────────┘
```

---

## 3. GETTING STARTED

### 3.1 Installation

```bash
# From the bench directory
bench get-app https://github.com/dashrath199/agri_coldchain.git
bench --site your-site.com install-app agri_coldchain
bench --site your-site.com migrate
```

### 3.2 Developer Mode (Recommended for exploring fixtures)

```bash
bench --site your-site.com set-config developer_mode 1
bench --site your-site.com migrate
```

### 3.3 Role Setup — Manual step required

Unlike a typical app, **this repo does not create its own Roles**. DocType permissions (Section 2.2's three custom DocTypes, plus the notification logic in [Section 10](#10-notifications--alerts)) all reference four role names by string:

- **Cold Storage Manager**
- **Quality Inspector**
- **Warehouse Operator**
- **Supplier** (standard ERPNext role, already exists)

The first three must be created manually (Desk → Role → New) and assigned to users before permissions or FEFO override behavior will work as documented. See [13.3](#13-known-limitations) for why this matters more than it might look.

### 3.4 Optional: Agmarknet API Key

The daily mandi-price sync task looks for a site-config key:

```bash
bench --site your-site.com set-config agmarknet_api_key "your_key_here"
```

Without it, `sync_mandi_prices()` logs an error and exits — see [13.6](#13-known-limitations) for what it does even *with* a key configured (spoiler: still a placeholder).

### 3.5 Load Demo Data (manual — not automatic)

```bash
bench --site your-site.com execute agri_coldchain.demo_data.execute
```

> Unlike a patch-driven seeder, this is **not** run automatically on install (`patches.txt` is empty). You must run it explicitly. To remove it again:
>
> ```bash
> bench --site your-site.com execute agri_coldchain.cleanup_data.execute
> ```

---

## 4. FEATURE 1: QUALITY INSPECTION → SHELF LIFE ADJUSTMENT

### 4.1 Purpose

Not every batch of a perishable item is equally fresh. A poorly-graded batch should carry a shorter shelf life than the item's default, and every downstream feature (risk reports, FEFO ordering, expiry date) should use that *adjusted* life, not the optimistic default.

### 4.2 Workflow

1. Item master carries the rulebook: `custom_base_shelf_life_days`, `custom_max_safe_temp_c`, `custom_requires_quality_inspection`.
2. Inspector opens **Quality Inspection**, fills `custom_moisture_percent`, `custom_visual_defect_percent`, and assigns `custom_grade` (A / B / C / Reject) — required field.
3. On `validate`, `compute_adjusted_shelf_life()` reads the **standard ERPNext** `shelf_life_in_days` field on Item (not the custom field) and computes:

   ```python
   grade_multipliers = {"A": 1.0, "B": 0.7, "C": 0.4, "Reject": 0.0}
   custom_adjusted_shelf_life_days = int(shelf_life_in_days * grade_multipliers[custom_grade])
   ```

   Example: 7-day tomato, Grade B → `int(7 × 0.7) = 4` days.
4. On `on_save`, if `custom_grade == "Reject"`, `on_save_quality_check()` notifies users with the Cold Storage Manager role (see caveat in [10.2](#10-notifications--alerts)).
5. Two separate hooks push the grade onto the Batch record — see [13.4](#13-known-limitations) for why there are two:
   - `push_quality_data_to_batch` — Purchase Receipt `before_submit`
   - `set_batch_metadata_from_qi` — Serial and Batch Bundle `after_insert`

   Both write `batch.custom_grade`, `batch.custom_adjusted_shelf_life_days`, and recompute `batch.expiry_date = manufacturing_date + adjusted_shelf_life_days` via `db_set`.

> **Field reference note:** `compute_adjusted_shelf_life()` reads the item's *base* `shelf_life_in_days`, while the [Batches Nearing Expiry](#8-reports) risk query in `tasks.py` also reads `shelf_life_in_days` (not the batch's adjusted value) for its `risk_pct` calculation. So a batch's **displayed spoilage risk %** and its **actual expiry date** can be computed from two different shelf-life numbers.

---

## 5. FEATURE 2: FEFO ENFORCEMENT ON DELIVERY NOTES

### 5.1 Purpose

First Expiry, First Out: the batch closest to expiring must ship before a fresher batch of the same item, even if the fresher batch arrived earlier.

### 5.2 Workflow

`validate_fefo()` runs on every Delivery Note `validate` (skipped for returns):

1. For each item line with a `serial_and_batch_bundle`, look up every batch entry in the bundle.
2. For each batch, run `_get_oldest_batch(item_code, warehouse)` — a SQL query joining `Serial and Batch Bundle` → `Serial and Batch Entry` → `Batch`, filtered to submitted bundles with unexpired, in-stock quantity, ordered by `manufacturing_date ASC`.
3. If the selected batch isn't the oldest available:
   - **Cold Storage Manager role** → `frappe.msgprint()` warning (orange, non-blocking) + `_log_fefo_override()` writes a `Notification Log` entry tagged `"FEFO Override — Delivery Note ..."`.
   - **Any other role** → `frappe.throw()` blocks the save entirely.
4. On `on_submit`, `on_submit_fefo_override_check()` re-queries `Notification Log` for override entries tied to this Delivery Note and emails a summary — but only to users found via `role_profile_name = "Cold Storage Manager"` (see [13.2](#13-known-limitations)).

### 5.3 Where to see it

- **FEFO Override Log** report parses these `Notification Log` entries and shows Selected Batch vs. Oldest Available Batch, who overrode, and when.
- Try it: on a Delivery Note, manually pick a batch that isn't the oldest for that item+warehouse and save as Administrator (which holds every role).

---

## 6. FEATURE 3: TRANSIT TEMPERATURE BREACH DETECTION

### 6.1 Purpose

Prove — or disprove — that cold chain was maintained during transport, and identify which transporter is responsible when it wasn't.

### 6.2 Workflow

1. Transporter (or a warehouse operator on their behalf) creates a **Delivery Transit Log**: `delivery_note`, `transporter_name`, `vehicle_no`, `dispatch_temp`, `arrival_temp`.
2. On `validate`, `check_temperature_breach()`:
   ```python
   safe_temp = _get_safe_temp_threshold(delivery_note)  # first item's custom_max_safe_temp_c
   temperature_breach = 1 if arrival_temp > safe_temp else 0
   ```
   `temperature_breach` is `read_only` in the doctype JSON — it can only be set by this hook, never typed directly.
3. On `on_save`, if a breach was detected, `on_save_breach_notification()` emails everyone found via `role_profile_name` = "Quality Inspector" or "Cold Storage Manager" (again, see [13.2](#13-known-limitations)) with the transit log, transporter, vehicle, and both temperatures.

> **Single-item threshold:** `_get_safe_temp_threshold()` returns the **first** item's `custom_max_safe_temp_c` on the Delivery Note and stops there. A mixed-item shipment (e.g. milk at 6°C and frozen peas at -10°C on the same DN) is checked against only one of those thresholds, not each item independently.

### 6.3 Where to see it

- **❄️ Cold Storage Health** → Delivery Transit Log (list)
- **🔍 Reports & Analytics** → Transit Breach Log (filtered to `temperature_breach = 1`)

---

## 7. FEATURE 4: COLD STORAGE CAPACITY & MANDI PRICE REFERENCE

### 7.1 Cold Storage Unit

`ColdStorageUnit.validate()` runs two checks:
- `capacity_mt` must be greater than zero.
- The linked `warehouse` cannot be a group warehouse (`frappe.throw` if `warehouse.is_group`).

Two computed methods:
- `get_current_stock_kg()` — `SUM(actual_qty)` from `tabBin` for the linked warehouse.
- `get_utilization_percent()` — `min(100.0, stock_kg / (capacity_mt × 1000) × 100)`, **capped at 100%** for display.
- `is_over_capacity()` — `stock_kg > capacity_mt × 1000`, **uncapped**, used for the daily alert.

> Because one is capped and the other isn't, a unit that's genuinely at 150% of capacity will still show "100%" on the utilization report while correctly triggering the over-capacity email alert — the two numbers can disagree.

### 7.2 Mandi Price Reference

Simple reference data (`commodity`, `market_name`, `price_date`, `min_price`, `max_price`, `modal_price`) used by the Sale vs. Mandi Price report to compare your selling rate against the day's market rate. See [13.6](#13-known-limitations) for the state of the sync task that's meant to populate it.

---

## 8. REPORTS

| Report | Ref DocType | Type | What it answers |
|---|---|---|---|
| Batches Nearing Expiry | Serial and Batch Bundle | Script | Which batches are ≥70% through shelf life (`get_high_risk_batches()` in `tasks.py`) |
| Cold Storage Utilization | Cold Storage Unit | Script | % capacity filled per unit, by zone |
| Sale Price vs Modal Mandi Price | Sales Invoice | Script | Selling rate vs. that day's modal mandi price |
| Supplier Grading & Settlement | Purchase Receipt | Script | Grade distribution and settlement recommendation, by supplier |
| FEFO Override Log | Delivery Note | Script | Parses Notification Log entries for FEFO overrides (audit trail) |
| Transit Breach Log | Delivery Transit Log | Script | All logs where `temperature_breach = 1` |
| Spoilage Loss Value by Commodity/Month | Stock Entry | Script | `ABS(qty) × valuation_rate` for Material Issue write-offs, grouped by month |

> ⚠️ See [13.5](#13-known-limitations) — the report folders on disk currently include duplicate/orphaned copies of three of these that should be cleaned up before relying on `bench migrate` to sync them cleanly.

---

## 9. WORKSPACE NAVIGATION

**Cold Chain Operations** workspace (icon: `cold-chain`, public, 22 shortcuts, 5 sections):

| Section | Shortcuts |
|---|---|
| ❄️ Cold Storage Health | Cold Storage Units, Delivery Transit Log, Mandi Prices, Perishable Items |
| 📦 Intake & Quality | Goods Received (PR), Purchase Orders, Quality Inspection, Suppliers |
| 🚛 Dispatch & Sales | Delivery Notes, Sales Orders, Sales Invoices, New Transit Log |
| 📊 Stock & Batches | Stock Entries, Batch Records, FEFO Override Log, Stock Ageing |
| 🔍 Reports & Analytics | Batch Spoilage Risk, Cold Storage Utilization, Sale vs Mandi Price, Supplier Grading, Transit Breach Log, Spoilage Loss Report |

**Verified from the workspace fixture:** the workspace JSON itself has 22 shortcuts but **0 charts and 0 links wired in** — the 5 Dashboard Charts and 5 Number Cards exist as separate fixture records (`dashboard_chart_records.json`, `number_card_records.json`) but are not attached to this workspace page. This matches the honest note already in the app: it's a real, pending polish item, not a documentation error.

---

## 10. NOTIFICATIONS & ALERTS

| Trigger | Handler | Recipients (as coded) |
|---|---|---|
| FEFO override logged | `_log_fefo_override` → Notification Log | `for_user: "Administrator"` only |
| DN submitted with overrides | `on_submit_fefo_override_check` | Users with `role_profile_name = "Cold Storage Manager"` |
| QI graded "Reject" | `on_save_quality_check` | Users with `role_profile_name = "Cold Storage Manager"` |
| Temperature breach | `on_save_breach_notification` | Users with `role_profile_name` = "Quality Inspector" or "Cold Storage Manager" |
| Batch ≥70% through shelf life (daily) | `check_spoilage_risk_notifications` → `_send_spoilage_alert` | `for_user: "Administrator"` only |
| Cold storage unit over capacity (daily) | `check_cold_storage_capacity_alerts` → `_send_capacity_alert` | Users with `role_profile_name = "Cold Storage Manager"` |

> ⚠️ **`role_profile_name` is not the same as having a Role.** See [13.2](#13-known-limitations) — every lookup in this table except the two "Administrator only" rows filters `User.role_profile_name`, which is a single Role Profile assignment, not the multi-Role membership that DocType permissions in [Section 3.3](#3-getting-started) actually use. As written, these email/notification lookups will return no recipients unless a Role Profile of that exact name is separately created and assigned — a different, additional step from creating the Role itself.

---

## 11. SETUP & CONFIGURATION (FIXTURES)

`hooks.py` declares these fixtures, synced on install/migrate, in this order (Number Cards and Dashboard Charts intentionally precede Workspace for link validation):

```python
fixtures = [
    {"dt": "Number Card", "filters": [["module", "=", "Agri Cold Chain"]]},
    {"dt": "Dashboard Chart", "filters": [["module", "=", "Agri Cold Chain"]]},
    {"dt": "Custom Field", "filters": [["module", "=", "Agri Cold Chain"]]},
    {"dt": "Workspace", "filters": [["name", "=", "Cold Chain Operations"]]},
    {"dt": "Print Format", "filters": [["name", "=", "HACCP FSSAI Batch Certificate"]]},
]
```

> Note what's **not** in this list: **Role**. The three custom roles referenced throughout the app (Section 3.3) are not exported as a fixture, so a fresh install does not create them — they must be added manually.

Also declared in `hooks.py`, outside `fixtures`:
- `permission_query_conditions` / `has_permission` on Purchase Receipt and Quality Inspection — restricts Supplier-portal users to their own records (`permissions.py`).
- `scheduler_events` — daily `sync_mandi_prices`; daily_long `check_spoilage_risk_notifications`, `check_cold_storage_capacity_alerts`.
- `webhooks` — a dict named `"Farmer Settlement Notice"` pointing at Purchase Receipt `on_submit`. This is **not** a documented Frappe `hooks.py` key (real Frappe Webhooks are Webhook DocType records, created via the Desk UI or API, not declared in `hooks.py`), so this entry does not appear to register anything at runtime — worth verifying against your Frappe version before relying on it.

---

## 12. DEMO DATA

Seeded by running `agri_coldchain.demo_data.execute` manually (see [3.5](#3-getting-started)). Builds data directly via `frappe.get_doc(...).insert()` rather than going through full document submission flows, "to avoid version-dependent validation errors" (per the script's own docstring):

- **6 Item Groups**, **4 Warehouses**, **5 Suppliers**, **4 Customers**, **14 Items**
- **8 Batches** — including Hybrid Tomatoes, Grade B, manufactured 6 days ago (7-day base shelf life, 4-day adjusted — already high-risk by design)
- **8 Stock Entries**, **7 Quality Inspections** (drafts), **3 Sales Invoices**, **2 Delivery Notes**
- **3 Delivery Transit Logs** — two clean (Swift Cargo Logistics 4.5→6.0°C; Rapid Chill Transport 3.8→4.2°C) and one seeded breach (Highway Kold Carriers 4.5→6.5°C against milk's 6.0°C threshold) — see the earlier `demo_data.py` edit in this conversation
- **1 Spoilage write-off** — 25 kg Spent Hen Meat (Grade C), Material Issue

To remove it: `bench --site your-site.com execute agri_coldchain.cleanup_data.execute` (deletes in dependency order: transit logs → notification logs → stock entries → delivery notes → sales invoices → quality inspections → batches → mandi prices → cold storage units → items → customers/suppliers → warehouses → item groups).

---

## 13. KNOWN LIMITATIONS

This section is included deliberately — these are findings from reading the actual source in this repo, not hypothetical concerns.

### 13.1 `doc_events` hook paths point to submodules that don't exist

`hooks.py` wires automation like this:

```python
doc_events = {
    "Delivery Note": {"validate": "agri_coldchain.event_handlers.delivery_note.validate_fefo"},
    "Purchase Receipt": {"before_submit": "agri_coldchain.event_handlers.purchase_receipt.push_quality_data_to_batch"},
    "Quality Inspection": {"validate": "agri_coldchain.event_handlers.quality_inspection.compute_adjusted_shelf_life", ...},
    "Delivery Transit Log": {"validate": "agri_coldchain.event_handlers.delivery_transit_log.check_temperature_breach", ...},
    "Serial and Batch Bundle": {"after_insert": "agri_coldchain.event_handlers.batch_bundle.set_batch_metadata_from_qi"},
}
```

But every one of those functions is defined directly inside the single flat file `agri_coldchain/event_handlers.py` — there is no `event_handlers/delivery_note.py`, `event_handlers/purchase_receipt.py`, etc. As configured, Frappe would fail to resolve these dotted paths (there is no `delivery_note` attribute on the `event_handlers` module). This is the app's core selling point — FEFO enforcement, breach detection, shelf-life computation, batch metadata sync — so this is the single highest-priority fix. Either flatten the paths in `hooks.py` to `agri_coldchain.event_handlers.validate_fefo` (etc.), or split `event_handlers.py` into the submodule package the hooks currently expect.

### 13.2 Notification recipient lookups filter the wrong field

Every alert path in [Section 10](#10-notifications--alerts) (except the two Administrator-only ones) does:

```python
frappe.db.get_all("User", filters={"role_profile_name": "Cold Storage Manager", "enabled": 1}, pluck="email")
```

`role_profile_name` on the User doctype is a single **Role Profile** assignment (a named bundle of roles), not the same thing as a user simply *having* the Role "Cold Storage Manager" via the standard multi-role assignment used everywhere else in this app (including its own DocType permissions in Section 2.2). Unless someone separately creates a Role Profile literally named "Cold Storage Manager" / "Quality Inspector" and assigns it to users, these queries return an empty list and the alert silently goes to nobody — no error, no log, just no email.

### 13.3 The Roles the app depends on are never created by the app

Cold Storage Manager, Quality Inspector, and Warehouse Operator are referenced throughout (DocType permissions, `_handle_fefo_violation`'s manager-vs-operator branching, all the notification lookups above) but there's no `Role` entry in `fixtures`, no patch, and no `after_install` hook that creates them. This matches the open roadmap item ("Roles & Permissions") — until they're created manually, permission rows referencing them are effectively inert and the FEFO manager-override path can only ever be exercised by Administrator (who implicitly holds every role).

### 13.4 Duplicate batch-metadata push

`push_quality_data_to_batch` (Purchase Receipt `before_submit`) and `set_batch_metadata_from_qi` (Serial and Batch Bundle `after_insert`) both independently look up the same draft Quality Inspection and write the same two fields (`custom_grade`, `custom_adjusted_shelf_life_days`) plus recompute `expiry_date`, via `db_set`. Harmless if both eventually agree, but it's two independent code paths doing the same job with no single source of truth — the kind of duplication that's easy to let drift out of sync during a future edit.

### 13.5 Orphaned/duplicate report folders on disk

The `report/` directory currently contains, for three logical reports, two folders each — one with the old auto-generated slug and one renamed to the current name:

- `sale_price_vs._modal_mandi_price/` **and** `sale_price_vs_modal_mandi_price/`
- `supplier_grading_&_settlement/` **and** `supplier_grading_settlement/` (both registered under the identical Report name "Supplier Grading & Settlement")
- `spoilage_loss_value_by_commodity/` (a stray folder containing only an empty `month/__init__.py`, left behind by a rename) **and** the real `spoilage_loss_value_by_commodity_month/`

Worth deleting the stale copies before a `bench migrate` on a fresh site, to avoid a duplicate-name conflict when report fixtures sync.

### 13.6 Mandi price sync is a placeholder, even when configured

`sync_mandi_prices()` doesn't call the Agmarknet API despite `requests` being a declared dependency. With no `agmarknet_api_key` configured, it logs an error and returns. With one configured, it still doesn't call the API — it fabricates one flat record per sampled item (`min_price=1000, max_price=1200, modal_price=1100`, market name "Sample Mandi") every day. The real API call is left as a comment for a future implementation.

### 13.7 Utilization display caps at 100%, capacity alert doesn't

`Cold Storage Unit.get_utilization_percent()` returns `min(100.0, ...)`, so the Cold Storage Utilization report will show "100%" for a unit at 110% or 300% of capacity. `is_over_capacity()` (used by the daily alert) correctly compares the uncapped numbers, so the alert can fire while the report shows a unit at a comfortable-looking 100%.

### 13.8 No automated test suite

There is no test directory or `bench run-tests` coverage in this repo for the FEFO logic, shelf-life math, breach detection, or the notification lookups above — the kind of regression in 13.1–13.4 would not be caught automatically on a future change.

---

## 14. TROUBLESHOOTING

### 14.1 Common Issues

| Issue | Cause | Solution |
|---|---|---|
| App not found during install | App not in `apps.txt` | `echo "agri_coldchain" >> sites/apps.txt` |
| `ModuleNotFoundError` on Delivery Note / Quality Inspection / Delivery Transit Log save | `hooks.py` doc_events point to non-existent submodules — see [13.1](#13-known-limitations) | Fix the dotted paths in `hooks.py` to match the flat `event_handlers.py`, or split it into the submodule layout the hooks expect |
| FEFO alerts / breach emails never arrive | Recipient lookups filter `role_profile_name`, not Role — see [13.2](#13-known-limitations) | Create and assign a matching Role Profile, or patch the lookups to use `frappe.get_all("Has Role", ...)` |
| FEFO override always blocks, even for managers | "Cold Storage Manager" Role was never created / assigned — see [13.3](#13-known-limitations) | Create the Role manually and assign it to the relevant users |
| DocTypes not created during migrate | Developer Mode is off | `bench --site site set-config developer_mode 1` then `bench --site site migrate` |
| Duplicate report name error on migrate | Orphaned report folders — see [13.5](#13-known-limitations) | Delete the stale duplicate folder(s) before migrating |
| Demo data not loading | It's not automatic — see [3.5](#3-getting-started) | Run `bench --site site execute agri_coldchain.demo_data.execute` |
| Mandi Price Reference has no real market data | Sync task is a placeholder — see [13.6](#13-known-limitations) | Implement the actual Agmarknet API call in `tasks.py` |
| Reports not showing | Reports auto-discovered but cache stale | `bench clear-cache` then `bench --site site migrate` |

### 14.2 Force Sync DocTypes (if missing)

```bash
bench --site your-site.com console
```
```python
from frappe.model.sync import sync_for
sync_for("agri_coldchain")
frappe.db.commit()
exit()
```

### 14.3 Full Re-install (Last Resort)

```bash
bench --site your-site.com uninstall-app agri_coldchain
bench --site your-site.com install-app agri_coldchain
bench --site your-site.com migrate
bench --site your-site.com clear-cache
```

---

## 15. APPENDIX

### A. Role Permissions (as declared in DocType JSON — Roles must be created manually, see 13.3)

| Role | Cold Storage Unit | Delivery Transit Log | Mandi Price Reference |
|---|:---:|:---:|:---:|
| Cold Storage Manager | Full (incl. submit/amend/cancel) | Full | Full |
| Quality Inspector | Create/Write, no Delete | Create/Write, no Delete | Read only |
| Warehouse Operator | Create/Write, no Delete | Create/Write, no Delete | Read only |
| Supplier | Read + Print only | — | — |

### B. Custom Field Reference

#### On Item
| Field | Type | Notes |
|---|:---:|---|
| `custom_base_shelf_life_days` | Int | Default shelf life for this product |
| `custom_requires_quality_inspection` | Check | Whether intake requires inspection |
| `custom_max_safe_temp_c` | Float | Breach threshold used by transit logs |

#### On Batch
| Field | Type | Read-only |
|---|:---:|:---:|
| `custom_grade` | Select (A/B/C/Reject) | ✅ |
| `custom_adjusted_shelf_life_days` | Int | ✅ |

#### On Quality Inspection
| Field | Type | Required | Read-only |
|---|:---:|:---:|:---:|
| `custom_moisture_percent` | Float | ❌ | ❌ |
| `custom_visual_defect_percent` | Float | ❌ | ❌ |
| `custom_grade` | Select (A/B/C/Reject) | ✅ | ❌ |
| `custom_adjusted_shelf_life_days` | Int | ❌ | ✅ (computed) |

### C. Custom DocType Field Reference

#### Cold Storage Unit
| Field | Type | Required | Notes |
|---|:---:|:---:|---|
| Unit Name | Data | ✅ (unique) | Autoname source |
| Capacity (MT) | Float | ❌ | Must be > 0 |
| Current Temperature Range | Data | ❌ | Free text, e.g. "-18 to -22 °C" |
| Zone Type | Select | ❌ | Frozen / Chilled / Ambient |
| Warehouse | Link → Warehouse | ❌ | Must be non-group |
| Is Active | Check | ❌ | |

#### Delivery Transit Log
| Field | Type | Required | Notes |
|---|:---:|:---:|---|
| Delivery Note | Link → Delivery Note | ✅ | |
| Transporter Name | Data | ❌ | |
| Vehicle Number | Data | ❌ | |
| Dispatch Temp (°C) | Float | ❌ | |
| Arrival Temp (°C) | Float | ❌ | |
| Temperature Breach | Check | ❌ | Read-only, auto-set |

#### Mandi Price Reference
| Field | Type | Required | Notes |
|---|:---:|:---:|---|
| Commodity | Link → Item | ✅ | |
| Market Name | Data | ❌ | |
| Price Date | Date | ✅ | |
| Min / Max / Modal Price | Currency | ❌ | |

### D. Related Documents

- Frappe Framework Documentation: https://frappeframework.com/docs
- ERPNext Documentation: https://docs.erpnext.com

### E. Repository

- **Repository:** https://github.com/dashrath199/agri_coldchain
- **License:** MIT © 2026 Your Organisation *(placeholder — update with real publisher details)*
- **Contact:** info@example.com *(placeholder — update with real contact)*

---

*End of README*
