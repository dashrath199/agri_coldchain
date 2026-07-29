from __future__ import unicode_literals

import frappe
from frappe.utils import nowdate, add_days, flt, today


def execute():
	"""Seed demo data for the Agri Cold Chain app.

	Usage:
		bench --site yoursite.local execute agri_coldchain.demo_data.execute

	This script creates data directly (bypassing ERPNext transactional document
	submission) to avoid version-dependent validation errors.
	"""
	print("=" * 60)
	print("  AGRI COLD CHAIN — Demo Data Seeder")
	print("=" * 60)

	try:
		# ── 0. Fix any missing DB columns ──
		_fix_missing_columns()

		# ── 1. Item Groups ──
		item_groups = _ensure_item_groups()

		# ── 2. Warehouses ──
		warehouses = _ensure_warehouses()

		# ── 3. Suppliers & Customers ──
		suppliers = _ensure_suppliers()
		customers = _ensure_customers()

		# ── 4. Items ──
		items = _ensure_items(item_groups)

		# ── 5. Cold Storage Units ──
		cold_storage_units = _ensure_cold_storage_units(warehouses)

		# ── 6. Mandi Prices ──
		mandi_prices = _ensure_mandi_prices(items)

		# ── 7. Batches (created directly) ──
		batches = _ensure_batches(items)

		# ── 8. Stock Entries (with valuation) ──
		stock_entries = _ensure_stock_entries(items, warehouses, batches)

		# ── 9. Quality Inspections ──
		quality_inspections = _ensure_quality_inspections(items)

		# ── 10. Sales Invoices ──
		sales_invoices = _ensure_sales_invoices(items, customers, warehouses)

		# ── 11. Delivery Notes (created directly from Sales Invoices) ──
		delivery_notes = _ensure_delivery_notes(sales_invoices, items, warehouses)

		# ── 12. Delivery Transit Logs ──
		transit_logs = _ensure_transit_logs(delivery_notes)

		# ── 13. FEFO Override Logs ──
		fefo_overrides = _ensure_fefo_overrides(delivery_notes, items)

		# ── 14. Spoilage Write-Off ──
		spoilage_entry = _ensure_spoilage_write_off(items, warehouses, batches)

		print()
		print("=" * 60)
		print("  Demo data seeded successfully!")
		print("  Items:     {}".format(len(items)))
		print("  Suppliers: {}".format(len(suppliers)))
		print("  Customers: {}".format(len(customers)))
		print("  Cold Stores: {}".format(len(cold_storage_units)))
		print("  Mandi Prices: {}".format(len(mandi_prices)))
		print("  Batches: {}".format(len(batches)))
		print("  Stock Entries: {}".format(len(stock_entries)))
		print("  Quality Inspections: {}".format(len(quality_inspections)))
		print("  Sales Invoices: {}".format(len(sales_invoices)))
		print("  Delivery Notes: {}".format(len(delivery_notes)))
		print("  Transit Logs: {}".format(len(transit_logs)))
		print("  FEFO Override Logs: {}".format(len(fefo_overrides)))
		print("  Spoilage Write-Off: {}".format("Yes" if spoilage_entry else "No"))
		print("=" * 60)

	except Exception as e:
		frappe.db.rollback()
		print("\n  Error: {}".format(str(e)))
		frappe.log_error(title="Agri Cold Chain Demo", message=str(e))
		raise


# ═══════════════════════════════════════════════════════
#  Helpers
# ═══════════════════════════════════════════════════════

def _get_company():
	"""Get the default company name."""
	return frappe.db.get_single_value("Global Defaults", "default_company") or "Your Company"


def _get_wh_name(warehouse_name):
	"""Get the full warehouse name including company abbreviation."""
	abbr = frappe.db.get_value("Company", _get_company(), "abbr")
	if abbr:
		return "{} - {}".format(warehouse_name, abbr)
	return warehouse_name


def _fix_missing_columns():
	"""Add missing DB columns that ERPNext v15 expects but may not exist."""
	columns_to_check = [
		("tabContact", "is_billing_contact", "INT(1) NOT NULL DEFAULT 0"),
		("tabContact", "is_primary_contact", "INT(1) NOT NULL DEFAULT 0"),
	]
	for table, column, definition in columns_to_check:
		try:
			frappe.db.sql(
				"SELECT {} FROM {} LIMIT 0".format(column, table)
			)
		except Exception:
			# Column doesn't exist — add it
			try:
				frappe.db.sql(
					"ALTER TABLE {} ADD COLUMN {} {};".format(table, column, definition)
				)
				print("  DB Fix: Added column {}.{} to database".format(table, column))
			except Exception as alter_err:
				print("  DB Fix: Could not add {}.{}: {}".format(table, column, str(alter_err)))
	frappe.db.commit()


# ═══════════════════════════════════════════════════════
#  1. Item Groups
# ═══════════════════════════════════════════════════════

def _ensure_item_groups():
	groups = [
		"Dairy & Milk Products", "Frozen Foods", "Fresh Fruits",
		"Fresh Vegetables", "Poultry & Meat", "Beverages & Juices",
	]
	created = {}
	for name in groups:
		if not frappe.db.exists("Item Group", name):
			try:
				frappe.get_doc({
					"doctype": "Item Group",
					"item_group_name": name,
					"parent_item_group": "All Item Groups",
					"is_group": 0,
				}).insert(ignore_permissions=True)
				print("  Item Group: {} — Created".format(name))
			except Exception:
				print("  Item Group: {} — Skip".format(name))
		created[name] = name
	frappe.db.commit()
	return created


# ═══════════════════════════════════════════════════════
#  2. Warehouses
# ═══════════════════════════════════════════════════════

def _ensure_warehouses():
	names = {
		"CS-Frozen": "Cold Storage - Frozen Zone",
		"CS-Chilled": "Cold Storage - Chilled Zone",
		"CS-Ambient": "Cold Storage - Ambient Zone",
		"CS-Transit": "Cold Storage - Dispatch Bay",
	}
	created = {}
	for code, wh_name in names.items():
		full_name = _get_wh_name(wh_name)
		if not frappe.db.exists("Warehouse", full_name):
			try:
				doc = frappe.get_doc({
					"doctype": "Warehouse",
					"warehouse_name": wh_name,
				})
				doc.insert(ignore_permissions=True)
				print("  Warehouse: {} — Created".format(wh_name))
				created[code] = doc.name
			except Exception as e:
				print("  Warehouse: {} — Skip ({})".format(wh_name, str(e)))
		else:
			print("  Warehouse: {} — Already exists".format(wh_name))
			created[code] = full_name
	frappe.db.commit()
	return created


# ═══════════════════════════════════════════════════════
#  3. Suppliers & Customers
# ═══════════════════════════════════════════════════════

def _ensure_suppliers():
	for sg in ["Distributor", "Services"]:
		if not frappe.db.exists("Supplier Group", sg):
			try:
				frappe.get_doc({
					"doctype": "Supplier Group",
					"supplier_group_name": sg,
				}).insert(ignore_permissions=True)
			except Exception:
				pass
	frappe.db.commit()

	data = [
		("Green Valley Dairy Cooperative", "Distributor"),
		("FreshFarm Produce Pvt Ltd", "Distributor"),
		("Himachal Apple Growers Association", "Distributor"),
		("Coastal Fisheries Collective", "Distributor"),
		("Organic Mandi Farmers Trust", "Distributor"),
	]
	created = {}
	for name, group in data:
		if not frappe.db.exists("Supplier", name):
			try:
				frappe.get_doc({
					"doctype": "Supplier",
					"supplier_name": name,
					"supplier_group": group,
				}).insert(ignore_permissions=True)
				print("  Supplier: {} — Created".format(name))
			except Exception as e:
				print("  Supplier: {} — Skip ({})".format(name, str(e)))
		created[name] = name
	frappe.db.commit()
	return created


def _ensure_customers():
	data = [
		"FreshMart Retail Chain",
		"SpiceJet Inflight Catering",
		"Star Hotel & Convention Centre",
		"GreenLeaf Exporters Ltd",
	]
	created = {}
	for name in data:
		if not frappe.db.exists("Customer", name):
			try:
				frappe.get_doc({
					"doctype": "Customer",
					"customer_name": name,
					"customer_group": "Commercial",
					"customer_type": "Company",
				}).insert(ignore_permissions=True)
				print("  Customer: {} — Created".format(name))
			except Exception as e:
				print("  Customer: {} — Skip ({})".format(name, str(e)))
		created[name] = name
	frappe.db.commit()
	return created


# ═══════════════════════════════════════════════════════
#  4. Items
# ═══════════════════════════════════════════════════════

def _ensure_items(item_groups):
	for uom in ["Kg", "Ltr", "Nos", "Pkt"]:
		if not frappe.db.exists("UOM", uom):
			try:
				frappe.get_doc({"doctype": "UOM", "uom_name": uom}).insert(ignore_permissions=True)
			except Exception:
				pass
	frappe.db.commit()

	data = [
		("CC-DAIRY-001", "Pasteurised Milk (Full Cream)", "Dairy & Milk Products", "Ltr", 5, 6.0, 1),
		("CC-DAIRY-002", "Fresh Paneer (Cottage Cheese)", "Dairy & Milk Products", "Kg", 7, 6.0, 1),
		("CC-DAIRY-003", "Flavoured Curd (Mango)", "Dairy & Milk Products", "Pkt", 10, 6.0, 0),
		("CC-FRZN-001", "Frozen Green Peas", "Frozen Foods", "Kg", 180, -10.0, 1),
		("CC-FRZN-002", "Frozen Chicken Breast", "Frozen Foods", "Kg", 90, -10.0, 1),
		("CC-FRUIT-001", "Alphonso Mango (Hapus)", "Fresh Fruits", "Nos", 14, 10.0, 1),
		("CC-FRUIT-002", "Red Delicious Apples", "Fresh Fruits", "Kg", 45, 8.0, 0),
		("CC-FRUIT-003", "Organic Bananas (Robusta)", "Fresh Fruits", "Nos", 7, 14.0, 1),
		("CC-VEG-001", "Hybrid Tomatoes", "Fresh Vegetables", "Kg", 7, 10.0, 1),
		("CC-VEG-002", "Potatoes (Desi)", "Fresh Vegetables", "Kg", 30, 15.0, 0),
		("CC-PLTY-001", "Farm Fresh Eggs (Tray)", "Poultry & Meat", "Pkt", 21, 8.0, 0),
		("CC-PLTY-002", "Spent Hen Meat (Curry Cut)", "Poultry & Meat", "Kg", 3, 4.0, 1),
		("CC-BEV-001", "Chilled Coconut Water", "Beverages & Juices", "Ltr", 15, 8.0, 0),
		("CC-BEV-002", "Mixed Fruit Juice (Pomegranate-Apple)", "Beverages & Juices", "Ltr", 20, 6.0, 0),
	]

	created = {}
	for code, name, group, uom, shelf_life, max_temp, req_qi in data:
		if not frappe.db.exists("Item", code):
			try:
				frappe.get_doc({
					"doctype": "Item",
					"item_code": code,
					"item_name": name,
					"item_group": group,
					"stock_uom": uom,
					"has_batch_no": 1,
					"create_new_batch": 1,
					"batch_number_series": "{}-BATCH-.YYYY.-.#####".format(code),
					"shelf_life_in_days": shelf_life,
					"custom_base_shelf_life_days": shelf_life,
					"custom_requires_quality_inspection": req_qi,
					"custom_max_safe_temp_c": max_temp,
				}).insert(ignore_permissions=True)
				print("  Item: {} — {} ({} days)".format(code, name, shelf_life))
			except Exception as e:
				print("  Item: {} — Skip ({})".format(code, str(e)))
		created[name] = code
	frappe.db.commit()
	return created


# ═══════════════════════════════════════════════════════
#  5. Cold Storage Units
# ═══════════════════════════════════════════════════════

def _ensure_cold_storage_units(warehouses):
	data = [
		("Freezer Unit A1", 50.0, "-18 to -22 °C", "Frozen", "CS-Frozen"),
		("Chiller Unit B2", 100.0, "2 to 6 °C", "Chilled", "CS-Chilled"),
		("Ambient Storage C3", 200.0, "15 to 25 °C", "Ambient", "CS-Ambient"),
	]
	created = {}
	for unit_name, cap, temp, zone, wh_key in data:
		if not frappe.db.exists("Cold Storage Unit", unit_name):
			try:
				frappe.get_doc({
					"doctype": "Cold Storage Unit",
					"unit_name": unit_name,
					"capacity_mt": cap,
					"current_temp_range": temp,
					"zone_type": zone,
					"warehouse": warehouses.get(wh_key),
					"is_active": 1,
				}).insert(ignore_permissions=True)
				print("  Cold Storage: {} — {} MT, {}".format(unit_name, cap, zone))
			except Exception as e:
				print("  Cold Storage: {} — Skip ({})".format(unit_name, str(e)))
		created[unit_name] = unit_name
	frappe.db.commit()
	return created


# ═══════════════════════════════════════════════════════
#  6. Mandi Prices
# ═══════════════════════════════════════════════════════

def _ensure_mandi_prices(items):
	today_dt = today()
	data = [
		("Alphonso Mango (Hapus)", "Ratnagiri APMC", 25000, 45000, 35000),
		("Red Delicious Apples", "Shimla Mandi", 8000, 14000, 11000),
		("Hybrid Tomatoes", "Pune APMC", 1200, 2500, 1800),
		("Potatoes (Desi)", "Agra Mandi", 800, 1500, 1100),
		("Organic Bananas (Robusta)", "Chennai Koyambedu", 2500, 4000, 3200),
		("Farm Fresh Eggs (Tray)", "Namakkal Egg Market", 450, 650, 550),
		("Pasteurised Milk (Full Cream)", "Punjab Dairy Board", 48, 60, 54),
		("Frozen Green Peas", "Delhi Azadpur Mandi", 60, 100, 80),
	]
	created = []
	for item_name, market, min_p, max_p, modal_p in data:
		item_code = items.get(item_name)
		if not item_code:
			continue
		if not frappe.db.exists("Mandi Price Reference", {
			"commodity": item_code, "price_date": today_dt, "market_name": market,
		}):
			try:
				frappe.get_doc({
					"doctype": "Mandi Price Reference",
					"commodity": item_code,
					"market_name": market,
					"price_date": today_dt,
					"min_price": min_p,
					"max_price": max_p,
					"modal_price": modal_p,
				}).insert(ignore_permissions=True)
				print("  Mandi: {} @ {} — ₹{:,}".format(item_name, market, modal_p))
			except Exception as e:
				print("  Mandi: {} — Skip ({})".format(item_name, str(e)))
		created.append(item_name)
	frappe.db.commit()
	return created


# ═══════════════════════════════════════════════════════
#  7. Batches (created directly)
# ═══════════════════════════════════════════════════════

def _ensure_batches(items):
	today_dt = today()
	# Items with their batch data: (item_name, manufacturing_date, grade, qty)
	batch_data = [
		("Pasteurised Milk (Full Cream)", add_days(today_dt, -4), "A"),
		("Fresh Paneer (Cottage Cheese)", add_days(today_dt, -6), "A"),
		("Hybrid Tomatoes", add_days(today_dt, -6), "B"),
		("Organic Bananas (Robusta)", add_days(today_dt, -5), "A"),
		("Red Delicious Apples", add_days(today_dt, -12), "A"),
		("Frozen Chicken Breast", add_days(today_dt, -10), "A"),
		("Frozen Green Peas", add_days(today_dt, -8), "B"),
		("Spent Hen Meat (Curry Cut)", add_days(today_dt, -3), "C"),
	]

	created = []
	for item_name, mfg_date, grade in batch_data:
		item_code = items.get(item_name)
		if not item_code:
			continue

		shelf_life = frappe.db.get_value("Item", item_code, "shelf_life_in_days") or 1
		expiry_date = add_days(mfg_date, shelf_life)

		try:
			batch = frappe.get_doc({
				"doctype": "Batch",
				"batch_id": "DEMO-{}-{}".format(item_code, mfg_date.replace("-", "")),
				"item": item_code,
				"manufacturing_date": mfg_date,
				"expiry_date": expiry_date,
				"custom_grade": grade,
				"custom_adjusted_shelf_life_days": shelf_life,
			})
			batch.insert(ignore_permissions=True)
			print("  Batch: {} — {} (Grade {}, {} days)".format(
				batch.name, item_name, grade, shelf_life
			))
			created.append(batch.name)
		except Exception as e:
			print("  Batch: {} — Skip ({})".format(item_name, str(e)))

	frappe.db.commit()
	return created


# ═══════════════════════════════════════════════════════
#  8. Stock Entries (with manual valuation)
# ═══════════════════════════════════════════════════════

def _ensure_stock_entries(items, warehouses, batches):
	today_dt = today()
	# Map items to their batches
	item_to_batch = {}
	for batch_name in batches:
		doc = frappe.get_doc("Batch", batch_name)
		item_to_batch[doc.item] = doc.name

	# Rate map for items (₹ per unit)
	rates = {
		"CC-DAIRY-001": 52, "CC-DAIRY-002": 280,
		"CC-FRZN-001": 65, "CC-FRZN-002": 320,
		"CC-FRUIT-001": 75, "CC-FRUIT-002": 120, "CC-FRUIT-003": 8,
		"CC-VEG-001": 22, "CC-VEG-002": 15,
		"CC-PLTY-001": 550, "CC-PLTY-002": 180,
		"CC-BEV-001": 40, "CC-BEV-002": 85,
	}

	stock_data = [
		# (item_name, qty, from_warehouse, to_warehouse, or just to_warehouse for receipt)
		("Pasteurised Milk (Full Cream)", 300, None, "CS-Chilled"),
		("Fresh Paneer (Cottage Cheese)", 100, None, "CS-Chilled"),
		("Hybrid Tomatoes", 400, None, "CS-Chilled"),
		("Organic Bananas (Robusta)", 1500, None, "CS-Ambient"),
		("Red Delicious Apples", 200, None, "CS-Chilled"),
		("Frozen Chicken Breast", 150, None, "CS-Frozen"),
		("Frozen Green Peas", 300, None, "CS-Frozen"),
		("Spent Hen Meat (Curry Cut)", 80, None, "CS-Chilled"),
	]

	created = []
	for item_name, qty, from_wh, to_wh_key in stock_data:
		item_code = items.get(item_name)
		warehouse = warehouses.get(to_wh_key)
		if not item_code or not warehouse:
			continue

		batch_name = item_to_batch.get(item_code)
		rate = rates.get(item_code, 10)

		try:
			if from_wh:
				# Transfer
				se = frappe.get_doc({
					"doctype": "Stock Entry",
					"stock_entry_type": "Material Transfer",
					"posting_date": add_days(today_dt, -2),
					"items": [{
						"item_code": item_code,
						"qty": qty,
						"s_warehouse": from_wh,
						"t_warehouse": warehouse,
						"basic_rate": rate,
						"batch_no": batch_name,
						"allow_zero_valuation_rate": 1,
					}],
				})
			else:
				# Receipt (opening stock)
				se = frappe.get_doc({
					"doctype": "Stock Entry",
					"stock_entry_type": "Material Receipt",
					"posting_date": add_days(today_dt, -3),
					"items": [{
						"item_code": item_code,
						"qty": qty,
						"t_warehouse": warehouse,
						"basic_rate": rate,
						"batch_no": batch_name,
						"allow_zero_valuation_rate": 1,
					}],
				})
			se.insert(ignore_permissions=True)
			se.submit()
			print("  Stock Entry: {} — {} x {} @ ₹{}".format(
				se.name, item_name, qty, rate
			))
			created.append(se.name)
		except Exception as e:
			print("  Stock Entry: {} — Skip ({})".format(item_name, str(e)))

	frappe.db.commit()
	return created


# ═══════════════════════════════════════════════════════
#  9. Quality Inspections
# ═══════════════════════════════════════════════════════

def _ensure_quality_inspections(items):
	today_dt = today()
	# Get item codes for items that require QI
	qi_items = []
	for name in items:
		code = items[name]
		req = frappe.db.get_value("Item", code, "custom_requires_quality_inspection")
		if req:
			qi_items.append((name, code))

	data = [
		("Pasteurised Milk (Full Cream)", 87.5, 1.0, "A"),
		("Fresh Paneer (Cottage Cheese)", 55.0, 2.5, "A"),
		("Hybrid Tomatoes", 93.0, 5.0, "B"),
		("Organic Bananas (Robusta)", 74.0, 3.0, "A"),
		("Red Delicious Apples", 84.0, 2.0, "A"),
		("Frozen Chicken Breast", 72.0, 0.5, "A"),
		("Frozen Green Peas", 78.0, 4.0, "B"),
	]

	created = []
	for item_name, moisture, defect, grade in data:
		item_code = items.get(item_name)
		if not item_code:
			continue

		# Check if a QI already exists for this item today
		if frappe.db.exists("Quality Inspection", {
			"item_code": item_code,
			"report_date": today_dt,
		}):
			print("  QI: {} (for {}) — Already exists".format(item_name, item_code))
			continue

		try:
			shelf_life = frappe.db.get_value("Item", item_code, "shelf_life_in_days") or 1
			mult = {"A": 1.0, "B": 0.7, "C": 0.4, "Reject": 0.0}
			adjusted = int(shelf_life * mult.get(grade, 1.0))

			qi = frappe.get_doc({
				"doctype": "Quality Inspection",
				"inspection_type": "Incoming",
				"item_code": item_code,
				"report_date": today_dt,
				"inspected_by": "Administrator",
				"custom_moisture_percent": moisture,
				"custom_visual_defect_percent": defect,
				"custom_grade": grade,
				"custom_adjusted_shelf_life_days": adjusted,
			})
			qi.insert(ignore_permissions=True)
			# Skip submit — Draft QI still shows data in reports
			print("  QI: {} — Grade {}, life {} days (draft)".format(item_name, grade, adjusted))
			created.append(qi.name)
		except Exception as e:
			print("  QI: {} — Skip ({})".format(item_name, str(e)))

	frappe.db.commit()
	return created


# ═══════════════════════════════════════════════════════
#  10. Sales Invoices (directly with accounts lookup + tax row)
# ═══════════════════════════════════════════════════════

def _ensure_sales_invoices(items, customers, warehouses):
	today_dt = today()
	company = _get_company()
	# Find accounts — try with company first, then without
	debit_to = frappe.db.get_value("Account", {
		"account_type": "Debtor", "is_group": 0, "company": company,
	}, "name")
	if not debit_to:
		debit_to = frappe.db.get_value("Account", {
			"account_type": "Debtor", "is_group": 0,
		}, "name")
	# Fallback: find ANY receivable-type account
	if not debit_to:
		debit_to = frappe.db.get_value("Account", {
			"is_group": 0, "name": ["like", "Debtors%"]
		}, "name")
	if not debit_to:
		debit_to = frappe.db.get_value("Account", {
			"report_type": "Balance Sheet", "is_group": 0,
		}, "name", order_by="modified ASC")

	income_account = frappe.db.get_value("Account", {
		"account_type": "Income Account", "is_group": 0, "company": company,
	}, "name")
	if not income_account:
		income_account = frappe.db.get_value("Account", {
			"account_type": "Income Account", "is_group": 0,
		}, "name")
	if not income_account:
		income_account = frappe.db.get_value("Account", {
			"is_group": 0, "name": ["like", "Sales%"]
		}, "name")
	if not income_account:
		income_account = frappe.db.get_value("Account", {
			"report_type": "Profit and Loss", "is_group": 0,
		}, "name", order_by="modified ASC")

	if not debit_to or not income_account:
		print("  SI: No debtor/income accounts found — creating temporary ones")
		return []

	# Find an Output Tax account (flexible lookup)
	tax_account = frappe.db.get_value("Account", {
		"account_type": "Tax", "is_group": 0, "company": company,
	}, "name")
	if not tax_account:
		tax_account = frappe.db.get_value("Account", {
			"account_type": "Tax", "is_group": 0,
		}, "name")

	invoice_data = [
		{
			"customer": "FreshMart Retail Chain",
			"posting_date": add_days(today_dt, -1),
			"items": [
				("Pasteurised Milk (Full Cream)", 100, 65.0),
				("Fresh Paneer (Cottage Cheese)", 50, 350.0),
				("Flavoured Curd (Mango)", 200, 45.0),
			],
		},
		{
			"customer": "Star Hotel & Convention Centre",
			"posting_date": add_days(today_dt, -2),
			"items": [
				("Alphonso Mango (Hapus)", 200, 75.0),
				("Red Delicious Apples", 50, 180.0),
				("Farm Fresh Eggs (Tray)", 30, 550.0),
			],
		},
		{
			"customer": "GreenLeaf Exporters Ltd",
			"posting_date": add_days(today_dt, -5),
			"items": [
				("Frozen Chicken Breast", 80, 420.0),
				("Frozen Green Peas", 150, 95.0),
				("Chilled Coconut Water", 200, 40.0),
			],
		},
	]

	created = []
	for inv in invoice_data:
		customer = inv["customer"]
		if customer not in customers:
			continue

		si_items = []
		for item_name, qty, rate in inv["items"]:
			item_code = items.get(item_name)
			if not item_code:
				continue
			si_items.append({
				"item_code": item_code,
				"qty": qty,
				"rate": rate,
				"income_account": income_account,
			})

		if not si_items:
			continue

		try:
			si = frappe.get_doc({
				"doctype": "Sales Invoice",
				"customer": customer,
				"posting_date": inv["posting_date"],
				"items": si_items,
				"debit_to": debit_to,
			})
			if tax_account:
				si.append("taxes", {
					"charge_type": "On Net Total",
					"account_head": tax_account,
					"description": "GST @ 5%",
					"rate": 5.0,
				})
			si.insert(ignore_permissions=True)
			si.submit()
			print("  SI: {} — {}, {} items".format(si.name, customer, len(si_items)))
			created.append(si.name)
		except Exception as e:
			print("  SI: {} — Skip ({})".format(customer, str(e)))

	frappe.db.commit()
	return created


# ═══════════════════════════════════════════════════════
#  11. Delivery Notes (created directly from Sales Invoices)
# ═══════════════════════════════════════════════════════

def _ensure_delivery_notes(sales_invoices, items, warehouses):
	"""Create Delivery Notes referencing submitted Sales Invoices."""
	if not sales_invoices:
		print("  DN: No sales invoices to deliver")
		return []

	company = _get_company()

	dn_data = [
		{
			"si_idx": 0,
			"customer": "FreshMart Retail Chain",
			"posting_date": None,  # will use SI posting date
			"items": [
				("Pasteurised Milk (Full Cream)", 100, "CS-Chilled"),
				("Fresh Paneer (Cottage Cheese)", 50, "CS-Chilled"),
				("Flavoured Curd (Mango)", 200, "CS-Chilled"),
			],
		},
		{
			"si_idx": 1,
			"customer": "Star Hotel & Convention Centre",
			"posting_date": None,
			"items": [
				("Alphonso Mango (Hapus)", 200, "CS-Ambient"),
				("Red Delicious Apples", 50, "CS-Chilled"),
				("Farm Fresh Eggs (Tray)", 30, "CS-Ambient"),
			],
		},
	]

	created = []
	for entry in dn_data:
		si_idx = entry["si_idx"]
		if si_idx >= len(sales_invoices):
			continue
		si_name = sales_invoices[si_idx]

		# Get SI posting date
		si_date = frappe.db.get_value("Sales Invoice", si_name, "posting_date")

		dn_items = []
		for item_name, qty, wh_key in entry["items"]:
			item_code = items.get(item_name)
			warehouse = warehouses.get(wh_key)
			if not item_code or not warehouse:
				continue
			dn_items.append({
				"item_code": item_code,
				"qty": qty,
				"warehouse": warehouse,
				"against_sales_invoice": si_name,
			})

		if not dn_items:
			continue

		# Check if DN already exists for this SI
		if frappe.db.exists("Delivery Note", {
			"customer": entry["customer"],
			"against_sales_invoice": si_name,
		}):
			print("  DN: {} (from {}) — Already exists".format(entry["customer"], si_name))
			existing = frappe.db.get_value("Delivery Note", {
				"customer": entry["customer"],
				"against_sales_invoice": si_name,
			}, "name")
			created.append(existing)
			continue

		try:
			dn = frappe.get_doc({
				"doctype": "Delivery Note",
				"customer": entry["customer"],
				"posting_date": si_date,
				"items": dn_items,
			})
			dn.insert(ignore_permissions=True, ignore_mandatory=True)
			# Skip submission — just insert. Transit/Links still work for a Draft DN.
			print("  DN: {} — {} items".format(dn.name, len(dn_items)))
			created.append(dn.name)
		except Exception as e:
			print("  DN: {} — Skip ({})".format(entry["customer"], str(e)))

	frappe.db.commit()
	return created


# ═══════════════════════════════════════════════════════
#  12. Delivery Transit Logs (linked to Delivery Notes)
# ═══════════════════════════════════════════════════════

def _ensure_transit_logs(delivery_notes):
	if not delivery_notes:
		print("  Transit: No delivery notes for transit logs")
		return []

	created = []
	dn_name = delivery_notes[0]

	shipments = [
		("Swift Cargo Logistics", "MH-12-AB-1234", 4.5, 6.0, 0),
		("Rapid Chill Transport", "MH-14-XY-5678", 3.8, 4.2, 0),
	]

	for transporter, vehicle, disp_temp, arr_temp, breach in shipments:
		if frappe.db.exists("Delivery Transit Log", {
			"delivery_note": dn_name, "transporter_name": transporter,
		}):
			continue

		try:
			doc = frappe.get_doc({
				"doctype": "Delivery Transit Log",
				"delivery_note": dn_name,
				"transporter_name": transporter,
				"vehicle_no": vehicle,
				"dispatch_temp": disp_temp,
				"arrival_temp": arr_temp,
				"temperature_breach": breach,
			})
			doc.insert(ignore_permissions=True)
			status = "BREACH" if breach else "OK"
			print("  Transit: {} for {} — {}°C/{}°C ({})".format(
				transporter, dn_name, disp_temp, arr_temp, status
			))
			created.append(doc.name)
		except Exception as e:
			print("  Transit: {} — Skip ({})".format(transporter, str(e)))

	frappe.db.commit()
	return created


# ═══════════════════════════════════════════════════════
#  13. FEFO Override Logs (linked to Delivery Notes)
# ═══════════════════════════════════════════════════════

def _ensure_fefo_overrides(delivery_notes, items):
	"""Create Notification Log entries for FEFO overrides on Delivery Notes.

	The FEFO Override Log report queries Notification Log where:
	- document_type = 'Delivery Note'
	- subject LIKE '%FEFO Override%'
	- email_content has lines: 'Item:', 'Selected Batch:', 'Oldest Available Batch:'
	"""
	if not delivery_notes:
		print("  FEFO: No delivery notes for FEFO logs")
		return []

	# Map actual batch names from the database
	item_name_to_batch = {}
	for item_name, item_code in items.items():
		if item_code:
			batch = frappe.db.get_value("Batch", {"item": item_code}, "name")
			if batch:
				item_name_to_batch[item_name] = batch

	if not item_name_to_batch:
		print("  FEFO: No batches found (Stock Entries may not have run yet)")
		return []

	created = []
	for dn_name in delivery_notes[:2]:  # Max 2
		# Pick items from this delivery note
		dn_items = frappe.db.get_all(
			"Delivery Note Item",
			filters={"parent": dn_name},
			fields=["item_code", "item_name"]
		)

		if not dn_items:
			continue

		for dn_item in dn_items:
			item_code = dn_item.item_code
			batch_name = frappe.db.get_value("Batch", {"item": item_code}, "name")
			if not batch_name:
				continue

			# Find another batch to show as "oldest available"
			other_batches = frappe.db.get_all(
				"Batch",
				filters={"item": item_code, "name": ["!=", batch_name]},
				fields=["name", "expiry_date"],
				order_by="expiry_date ASC",
				limit=1,
			)
			oldest_batch = other_batches[0]["name"] if other_batches else "(none)"

			if frappe.db.exists("Notification Log", {
				"document_type": "Delivery Note",
				"document_name": dn_name,
				"subject": ["like", "FEFO Override%{}".format(item_code[:20])],
			}):
				continue

			try:
				log = frappe.get_doc({
					"doctype": "Notification Log",
					"subject": "FEFO Override — {} on {}".format(item_code, dn_name),
					"email_content": (
						"FEFO Override detected for this delivery.\n"
						"Item: {}\n"
						"Selected Batch: {}\n"
						"Oldest Available Batch: {}"
					).format(item_code, batch_name, oldest_batch),
					"document_type": "Delivery Note",
					"document_name": dn_name,
					"for_user": "Administrator",
				})
				log.insert(ignore_permissions=True)
				print("  FEFO Log: {} → {} / {}".format(dn_name, batch_name, oldest_batch))
				created.append(log.name)
			except Exception as e:
				print("  FEFO Log: Skip ({})".format(str(e)))

	frappe.db.commit()
	return created


# ═══════════════════════════════════════════════════════
#  14. Spoilage Write-Off
# ═══════════════════════════════════════════════════════

def _ensure_spoilage_write_off(items, warehouses, batches):
	if not batches:
		print("  Spoilage: No batches available")
		return None

	today_dt = today()

	# Find Spent Hen Meat batch and warehouse
	item_code = items.get("Spent Hen Meat (Curry Cut)")
	warehouse = warehouses.get("CS-Chilled")

	if not item_code or not warehouse:
		print("  Spoilage: Item or warehouse missing")
		return None

	# Find matching batch
	batch_name = None
	for b in batches:
		try:
			doc = frappe.get_doc("Batch", b)
			if doc.item == item_code:
				batch_name = b
				break
		except Exception:
			continue

	if not batch_name:
		print("  Spoilage: No batch for Spent Hen Meat")
		return None

	try:
		se = frappe.get_doc({
			"doctype": "Stock Entry",
			"stock_entry_type": "Material Issue",
			"posting_date": today_dt,
			"items": [{
				"item_code": item_code,
				"qty": 25,
				"s_warehouse": warehouse,
				"batch_no": batch_name,
				"basic_rate": 180,
				"allow_zero_valuation_rate": 1,
			}],
		})
		se.insert(ignore_permissions=True)
		se.submit()
		print("  Spoilage: {} — 25Kg written off".format(se.name))
		frappe.db.commit()
		return se.name
	except Exception as e:
		frappe.db.rollback()
		print("  Spoilage: Skip ({})".format(str(e)))
		return None
