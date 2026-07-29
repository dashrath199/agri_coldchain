from __future__ import unicode_literals

import frappe
from frappe.utils import nowdate, add_days, add_months, flt, today


def execute():
	"""Seed demo data for the Agri Cold Chain app.

	Usage:
		bench --site yoursite.local execute agri_coldchain.demo_data.execute
	"""
	print("=" * 60)
	print("  AGRI COLD CHAIN — Demo Data Seeder")
	print("=" * 60)

	try:
		# ── 1. Item Groups ──
		item_groups = ensure_item_groups()

		# ── 2. Warehouses ──
		warehouses = ensure_warehouses()

		# ── 3. Suppliers ──
		suppliers = ensure_suppliers()

		# ── 4. Items (with batch/shelf-life fields) ──
		items = ensure_items(item_groups)

		# ── 5. Cold Storage Units ──
		cold_storage_units = ensure_cold_storage_units(warehouses)

		# ── 6. Mandi Price References ──
		mandi_prices = ensure_mandi_prices(items)

		# ── 7. Purchase Orders ──
		purchase_orders = ensure_purchase_orders(suppliers, items)

		# ── 8. Purchase Receipts + Batches ──
		purchase_receipts, batches = ensure_purchase_receipts(
			suppliers, items, warehouses, purchase_orders
		)

		# ── 9. Quality Inspections ──
		quality_inspections = ensure_quality_inspections(
			purchase_receipts, items
		)

		# ── 10. Stock Entries (transfers between units) ──
		stock_entries = ensure_stock_entries(items, warehouses)

		# ── 11. Sales Orders ──
		sales_orders = ensure_sales_orders(items, warehouses)

		# ── 12. Delivery Notes ──
		delivery_notes = ensure_delivery_notes(
			sales_orders, items, warehouses, batches
		)

		# ── 13. Delivery Transit Logs ──
		transit_logs = ensure_transit_logs(delivery_notes)

		# ── 14. Sales Invoices ──
		sales_invoices = ensure_sales_invoices(sales_orders)

		# ── 15. FEFO Override Log Entries ──
		fefo_overrides = ensure_fefo_overrides(delivery_notes, items)

		# ── 16. Spoilage Write-Off (Material Issue) ──
		spoilage_entry = ensure_spoilage_write_off(items, warehouses, batches)

		print()
		print("=" * 60)
		print("  Demo data seeded successfully!")
		print("  Items:     {}".format(len(items)))
		print("  Suppliers: {}".format(len(suppliers)))
		print("  Cold Stores: {}".format(len(cold_storage_units)))
		print("  Mandi Prices: {}".format(len(mandi_prices)))
		print("  Purchase Orders: {}".format(len(purchase_orders)))
		print("  PRs: {}  Batches: {}".format(len(purchase_receipts), len(batches)))
		print("  Quality Inspections: {}".format(len(quality_inspections)))
		print("  Stock Entries: {}".format(len(stock_entries)))
		print("  Sales Orders: {}".format(len(sales_orders)))
		print("  Delivery Notes: {}".format(len(delivery_notes)))
		print("  Transit Logs: {}".format(len(transit_logs)))
		print("  Sales Invoices: {}".format(len(sales_invoices)))
		print("  FEFO Override Logs: {}".format(len(fefo_overrides)))
		print("  Spoilage Write-Off Entry: {}".format("Yes" if spoilage_entry else "No"))
		print("=" * 60)

	except Exception as e:
		frappe.db.rollback()
		print("\n  Error seeding demo data: {}".format(str(e)))
		frappe.log_error(
			title="Agri Cold Chain Demo Data",
			message="Demo data seeding failed: {}".format(str(e)),
		)
		raise


# ═══════════════════════════════════════════════════════
#  1. Item Groups
# ═══════════════════════════════════════════════════════

def ensure_item_groups():
	"""Ensure Item Groups for perishable categories exist."""
	groups = [
		"Dairy & Milk Products",
		"Frozen Foods",
		"Fresh Fruits",
		"Fresh Vegetables",
		"Poultry & Meat",
		"Beverages & Juices",
		"Processed Foods",
	]

	created = {}
	for group_name in groups:
		if not frappe.db.exists("Item Group", group_name):
			try:
				frappe.get_doc({
					"doctype": "Item Group",
					"item_group_name": group_name,
					"parent_item_group": "All Item Groups",
					"is_group": 0,
				}).insert(ignore_permissions=True)
				print("  Item Group: {} — Created".format(group_name))
			except Exception as e:
				print("  Item Group: {} — Skip ({})".format(group_name, str(e)))
		else:
			print("  Item Group: {} — Already exists".format(group_name))
		created[group_name] = group_name

	frappe.db.commit()
	return created


# ═══════════════════════════════════════════════════════
#  2. Warehouses
# ═══════════════════════════════════════════════════════

def ensure_warehouses():
	"""Ensure warehouses for cold storage zones exist.

	Note: Warehouses are created as root-level (no parent_warehouse) to avoid
	link validation issues with Frappe's auto-naming convention
	(warehouse_name - company_abbr). The hierarchy is maintained via
	warehouse_name only for demo purposes.
	"""
	warehouse_names = {
		"CS-Frozen": "Cold Storage - Frozen Zone",
		"CS-Chilled": "Cold Storage - Chilled Zone",
		"CS-Ambient": "Cold Storage - Ambient Zone",
		"CS-Transit": "Cold Storage - Dispatch Bay",
	}

	created = {}
	for wh_code, wh_name in warehouse_names.items():
		if not frappe.db.exists("Warehouse", {"warehouse_name": wh_name}):
			try:
				doc = frappe.get_doc({
					"doctype": "Warehouse",
					"warehouse_name": wh_name,
					# Omit parent_warehouse to avoid link validation failures
					# due to Frappe's warehouse naming convention
				})
				doc.insert(ignore_permissions=True)
				print("  Warehouse: {} — Created".format(wh_name))
				created[wh_code] = doc.name
			except Exception as e:
				print("  Warehouse: {} — Skip ({})".format(wh_name, str(e)))
		else:
			existing = frappe.get_value("Warehouse", {"warehouse_name": wh_name}, "name")
			print("  Warehouse: {} — Already exists".format(wh_name))
			created[wh_code] = existing

	frappe.db.commit()
	return created


# ═══════════════════════════════════════════════════════
#  3. Suppliers
# ═══════════════════════════════════════════════════════

def ensure_suppliers():
	"""Ensure Suppliers (farmer cooperatives, distributors) exist."""
	# Ensure default supplier group exists
	for sg in ["Distributor", "Services"]:
		if not frappe.db.exists("Supplier Group", sg):
			try:
				frappe.get_doc({
					"doctype": "Supplier Group",
					"supplier_group_name": sg,
				}).insert(ignore_permissions=True)
			except Exception:
				pass

	for st in ["Company", "Individual"]:
		if not frappe.db.exists("Supplier Type", st):
			try:
				frappe.get_doc({
					"doctype": "Supplier Type",
					"supplier_type_name": st,
				}).insert(ignore_permissions=True)
			except Exception:
				pass
	frappe.db.commit()

	suppliers_data = [
		{
			"supplier_name": "Green Valley Dairy Cooperative",
			"supplier_group": "Distributor",
			"supplier_type": "Company",
			"email": "info@greenvalleydairy.in",
		},
		{
			"supplier_name": "FreshFarm Produce Pvt Ltd",
			"supplier_group": "Distributor",
			"supplier_type": "Company",
			"email": "orders@freshfarm.in",
		},
		{
			"supplier_name": "Himachal Apple Growers Association",
			"supplier_group": "Distributor",
			"supplier_type": "Company",
			"email": "info@himachalapple.in",
		},
		{
			"supplier_name": "Punjab Grain & Cold Storage Ltd",
			"supplier_group": "Distributor",
			"supplier_type": "Company",
			"email": "sales@punjabcold.in",
		},
		{
			"supplier_name": "Coastal Fisheries Collective",
			"supplier_group": "Distributor",
			"supplier_type": "Company",
			"email": "info@coastalfish.in",
		},
		{
			"supplier_name": "Organic Mandi Farmers Trust",
			"supplier_group": "Distributor",
			"supplier_type": "Company",
			"email": "farmers@organicmandi.in",
		},
	]

	created = {}
	for s_data in suppliers_data:
		name = s_data["supplier_name"]
		if not frappe.db.exists("Supplier", name):
			try:
				doc = frappe.get_doc({
					"doctype": "Supplier",
					"supplier_name": name,
					"supplier_group": s_data["supplier_group"],
					"supplier_type": s_data["supplier_type"],
				})
				doc.insert(ignore_permissions=True)
				print("  Supplier: {} — Created".format(name))
			except Exception as e:
				print("  Supplier: {} — Skip ({})".format(name, str(e)))
		else:
			print("  Supplier: {} — Already exists".format(name))
		created[name] = name

	frappe.db.commit()
	return created


# ═══════════════════════════════════════════════════════
#  4. Items
# ═══════════════════════════════════════════════════════

def ensure_items(item_groups):
	"""Ensure perishable Items exist with batch tracking and shelf life."""
	default_uom = frappe.db.get_single_value("Stock Settings", "stock_uom") or "Nos"

	# Ensure essential UOMs
	for uom_name in ["Kg", "Ltr", "Nos", "Pkt", "Box", "Crate"]:
		if not frappe.db.exists("UOM", uom_name):
			try:
				frappe.get_doc({
					"doctype": "UOM",
					"uom_name": uom_name,
				}).insert(ignore_permissions=True)
			except Exception:
				pass
	frappe.db.commit()

	items_data = [
		# Dairy
		{
			"item_code": "CC-DAIRY-001",
			"item_name": "Pasteurised Milk (Full Cream)",
			"item_group": "Dairy & Milk Products",
			"stock_uom": "Ltr",
			"shelf_life_days": 5,
			"max_safe_temp": 6.0,
			"requires_qi": 1,
			"description": "Full cream pasteurised milk, 1 litre packs, requires chilled storage",
		},
		{
			"item_code": "CC-DAIRY-002",
			"item_name": "Fresh Paneer (Cottage Cheese)",
			"item_group": "Dairy & Milk Products",
			"stock_uom": "Kg",
			"shelf_life_days": 7,
			"max_safe_temp": 6.0,
			"requires_qi": 1,
			"description": "Handmade fresh paneer blocks, 500g each",
		},
		{
			"item_code": "CC-DAIRY-003",
			"item_name": "Flavoured Curd (Mango)",
			"item_group": "Dairy & Milk Products",
			"stock_uom": "Pkt",
			"shelf_life_days": 10,
			"max_safe_temp": 6.0,
			"requires_qi": 0,
			"description": "Mango flavoured set curd, 200ml cups",
		},
		# Frozen
		{
			"item_code": "CC-FRZN-001",
			"item_name": "Frozen Green Peas",
			"item_group": "Frozen Foods",
			"stock_uom": "Kg",
			"shelf_life_days": 180,
			"max_safe_temp": -10.0,
			"requires_qi": 1,
			"description": "Blanched and frozen garden peas, 1kg packs",
		},
		{
			"item_code": "CC-FRZN-002",
			"item_name": "Frozen Chicken Breast",
			"item_group": "Frozen Foods",
			"stock_uom": "Kg",
			"shelf_life_days": 90,
			"max_safe_temp": -10.0,
			"requires_qi": 1,
			"description": "Boneless chicken breast, individually quick frozen",
		},
		# Fruits
		{
			"item_code": "CC-FRUIT-001",
			"item_name": "Alphonso Mango (Hapus)",
			"item_group": "Fresh Fruits",
			"stock_uom": "Nos",
			"shelf_life_days": 14,
			"max_safe_temp": 10.0,
			"requires_qi": 1,
			"description": "Premium Alphonso mangoes from Ratnagiri, graded",
		},
		{
			"item_code": "CC-FRUIT-002",
			"item_name": "Red Delicious Apples",
			"item_group": "Fresh Fruits",
			"stock_uom": "Kg",
			"shelf_life_days": 45,
			"max_safe_temp": 8.0,
			"requires_qi": 0,
			"description": "Premium red delicious apples from Himachal Pradesh",
		},
		{
			"item_code": "CC-FRUIT-003",
			"item_name": "Organic Bananas (Robusta)",
			"item_group": "Fresh Fruits",
			"stock_uom": "Nos",
			"shelf_life_days": 7,
			"max_safe_temp": 14.0,
			"requires_qi": 1,
			"description": "Organic robusta bananas from Tamil Nadu",
		},
		# Vegetables
		{
			"item_code": "CC-VEG-001",
			"item_name": "Hybrid Tomatoes",
			"item_group": "Fresh Vegetables",
			"stock_uom": "Kg",
			"shelf_life_days": 7,
			"max_safe_temp": 10.0,
			"requires_qi": 1,
			"description": "Premium hybrid tomatoes, graded for export",
		},
		{
			"item_code": "CC-VEG-002",
			"item_name": "Potatoes (Desi)",
			"item_group": "Fresh Vegetables",
			"stock_uom": "Kg",
			"shelf_life_days": 30,
			"max_safe_temp": 15.0,
			"requires_qi": 0,
			"description": "Desi variety potatoes from Uttar Pradesh",
		},
		# Poultry
		{
			"item_code": "CC-PLTY-001",
			"item_name": "Farm Fresh Eggs (Tray)",
			"item_group": "Poultry & Meat",
			"stock_uom": "Pkt",
			"shelf_life_days": 21,
			"max_safe_temp": 8.0,
			"requires_qi": 0,
			"description": "Farm fresh hen eggs, 30 per tray",
		},
		{
			"item_code": "CC-PLTY-002",
			"item_name": "Spent Hen Meat (Curry Cut)",
			"item_group": "Poultry & Meat",
			"stock_uom": "Kg",
			"shelf_life_days": 3,
			"max_safe_temp": 4.0,
			"requires_qi": 1,
			"description": "Fresh spent hen curry cut pieces, chilled",
		},
		# Beverages
		{
			"item_code": "CC-BEV-001",
			"item_name": "Chilled Coconut Water",
			"item_group": "Beverages & Juices",
			"stock_uom": "Ltr",
			"shelf_life_days": 15,
			"max_safe_temp": 8.0,
			"requires_qi": 0,
			"description": "Packed tender coconut water, 1 litre cartons",
		},
		{
			"item_code": "CC-BEV-002",
			"item_name": "Mixed Fruit Juice (Pomegranate-Apple)",
			"item_group": "Beverages & Juices",
			"stock_uom": "Ltr",
			"shelf_life_days": 20,
			"max_safe_temp": 6.0,
			"requires_qi": 0,
			"description": "Fresh pressed pomegranate-apple juice blend",
		},
	]

	created = {}
	for item_data in items_data:
		item_code = item_data["item_code"]
		if not frappe.db.exists("Item", item_code):
			try:
				doc = frappe.get_doc({
					"doctype": "Item",
					"item_code": item_code,
					"item_name": item_data["item_name"],
					"item_group": item_data["item_group"],
					"stock_uom": item_data["stock_uom"],
					"description": item_data["description"],
					"has_batch_no": 1,
					"create_new_batch": 1,
					"batch_number_series": "{}-BATCH-.YYYY.-.#####".format(item_code),
					"shelf_life_in_days": item_data["shelf_life_days"],
					"custom_base_shelf_life_days": item_data["shelf_life_days"],
					"custom_requires_quality_inspection": item_data["requires_qi"],
					"custom_max_safe_temp_c": item_data["max_safe_temp"],
				})
				doc.insert(ignore_permissions=True)
				print("  Item: {} — {} ({} days shelf life)".format(
					item_code, item_data["item_name"], item_data["shelf_life_days"]
				))
			except Exception as e:
				print("  Item: {} — Skip ({})".format(item_code, str(e)))
		else:
			print("  Item: {} — Already exists".format(item_code))
		created[item_data["item_name"]] = item_code

	frappe.db.commit()
	return created


# ═══════════════════════════════════════════════════════
#  5. Cold Storage Units
# ═══════════════════════════════════════════════════════

def ensure_cold_storage_units(warehouses):
	"""Ensure Cold Storage Units exist and link to warehouses."""
	units_data = [
		{
			"unit_name": "Freezer Unit A1",
			"capacity_mt": 50.00,
			"current_temp_range": "-18 to -22 °C",
			"zone_type": "Frozen",
			"warehouse_key": "CS-Frozen",
		},
		{
			"unit_name": "Chiller Unit B2",
			"capacity_mt": 100.00,
			"current_temp_range": "2 to 6 °C",
			"zone_type": "Chilled",
			"warehouse_key": "CS-Chilled",
		},
		{
			"unit_name": "Ambient Storage C3",
			"capacity_mt": 200.00,
			"current_temp_range": "15 to 25 °C",
			"zone_type": "Ambient",
			"warehouse_key": "CS-Ambient",
		},
	]

	created = {}
	for u_data in units_data:
		if not frappe.db.exists("Cold Storage Unit", u_data["unit_name"]):
			try:
				wh_name = warehouses.get(u_data["warehouse_key"])
				doc = frappe.get_doc({
					"doctype": "Cold Storage Unit",
					"unit_name": u_data["unit_name"],
					"capacity_mt": u_data["capacity_mt"],
					"current_temp_range": u_data["current_temp_range"],
					"zone_type": u_data["zone_type"],
					"warehouse": wh_name,
					"is_active": 1,
				})
				doc.insert(ignore_permissions=True)
				print("  Cold Storage Unit: {} — Created ({} MT, {})".format(
					u_data["unit_name"], u_data["capacity_mt"], u_data["zone_type"]
				))
			except Exception as e:
				print("  Cold Storage Unit: {} — Skip ({})".format(
					u_data["unit_name"], str(e)
				))
		else:
			print("  Cold Storage Unit: {} — Already exists".format(u_data["unit_name"]))
		created[u_data["unit_name"]] = u_data["unit_name"]

	frappe.db.commit()
	return created


# ═══════════════════════════════════════════════════════
#  6. Mandi Price References
# ═══════════════════════════════════════════════════════

def ensure_mandi_prices(items):
	"""Ensure Mandi Price Reference records exist."""
	today_dt = today()
	prices_data = [
		{"item_name": "Alphonso Mango (Hapus)", "market": "Ratnagiri APMC", "min_p": 25000, "max_p": 45000, "modal_p": 35000},
		{"item_name": "Red Delicious Apples", "market": "Shimla Mandi", "min_p": 8000, "max_p": 14000, "modal_p": 11000},
		{"item_name": "Hybrid Tomatoes", "market": "Pune APMC", "min_p": 1200, "max_p": 2500, "modal_p": 1800},
		{"item_name": "Potatoes (Desi)", "market": "Agra Mandi", "min_p": 800, "max_p": 1500, "modal_p": 1100},
		{"item_name": "Organic Bananas (Robusta)", "market": "Chennai Koyambedu", "min_p": 2500, "max_p": 4000, "modal_p": 3200},
		{"item_name": "Farm Fresh Eggs (Tray)", "market": "Namakkal Egg Market", "min_p": 450, "max_p": 650, "modal_p": 550},
		{"item_name": "Pasteurised Milk (Full Cream)", "market": "Punjab Dairy Board", "min_p": 48, "max_p": 60, "modal_p": 54},
		{"item_name": "Frozen Green Peas", "market": "Delhi Azadpur Mandi", "min_p": 60, "max_p": 100, "modal_p": 80},
	]

	created = []
	for p_data in prices_data:
		item_code = items.get(p_data["item_name"])
		if not item_code:
			print("  Mandi Price: {} — Item not found, skipping".format(p_data["item_name"]))
			continue

		if not frappe.db.exists("Mandi Price Reference", {
			"commodity": item_code,
			"price_date": today_dt,
			"market_name": p_data["market"],
		}):
			try:
				doc = frappe.get_doc({
					"doctype": "Mandi Price Reference",
					"commodity": item_code,
					"market_name": p_data["market"],
					"price_date": today_dt,
					"min_price": p_data["min_p"],
					"max_price": p_data["max_p"],
					"modal_price": p_data["modal_p"],
				})
				doc.insert(ignore_permissions=True)
				print("  Mandi Price: {} @ {} — Modal ₹{:,}".format(
					p_data["item_name"], p_data["market"], p_data["modal_p"]
				))
			except Exception as e:
				print("  Mandi Price: {} — Skip ({})".format(p_data["item_name"], str(e)))
		else:
			print("  Mandi Price: {} @ {} — Already exists".format(
				p_data["item_name"], p_data["market"]
			))
		created.append(p_data["item_name"])

	frappe.db.commit()
	return created


# ═══════════════════════════════════════════════════════
#  7. Purchase Orders
# ═══════════════════════════════════════════════════════

def ensure_purchase_orders(suppliers, items):
	"""Ensure Purchase Orders exist for perishable items."""
	today_dt = today()
	po_data = [
		{
			"supplier": "Green Valley Dairy Cooperative",
			"items": [
				("Pasteurised Milk (Full Cream)", 500, "Ltr", 52.0),
				("Fresh Paneer (Cottage Cheese)", 200, "Kg", 280.0),
				("Flavoured Curd (Mango)", 1000, "Pkt", 35.0),
			],
			"schedule": add_days(today_dt, 2),
		},
		{
			"supplier": "FreshFarm Produce Pvt Ltd",
			"items": [
				("Hybrid Tomatoes", 500, "Kg", 22.0),
				("Potatoes (Desi)", 1000, "Kg", 15.0),
				("Organic Bananas (Robusta)", 2000, "Nos", 8.0),
			],
			"schedule": add_days(today_dt, 5),
		},
		{
			"supplier": "Himachal Apple Growers Association",
			"items": [
				("Red Delicious Apples", 300, "Kg", 120.0),
			],
			"schedule": add_days(today_dt, 3),
		},
		{
			"supplier": "Coastal Fisheries Collective",
			"items": [
				("Frozen Chicken Breast", 250, "Kg", 320.0),
				("Frozen Green Peas", 400, "Kg", 65.0),
			],
			"schedule": add_days(today_dt, 4),
		},
	]

	created = []
	for po in po_data:
		supplier_name = po["supplier"]
		if not frappe.db.exists("Supplier", supplier_name):
			print("  PO: Supplier {} not found, skipping".format(supplier_name))
			continue

		# Check if a PO already exists for this supplier within 7 days
		existing_po = frappe.db.exists("Purchase Order", {
			"supplier": supplier_name,
			"transaction_date": [">=", add_days(today_dt, -7)],
		})
		if existing_po:
			print("  PO: {} — Already exists (recent)".format(supplier_name))
			if isinstance(existing_po, str):
				created.append(existing_po)
			continue

		po_items = []
		for item_name, qty, uom, rate in po["items"]:
			item_code = items.get(item_name)
			if not item_code:
				continue
			po_items.append({
				"item_code": item_code,
				"qty": qty,
				"uom": uom,
				"rate": rate,
				"schedule_date": po["schedule"],
			})

		if not po_items:
			continue

		try:
			doc = frappe.get_doc({
				"doctype": "Purchase Order",
				"supplier": supplier_name,
				"transaction_date": today_dt,
				"items": po_items,
			})
			doc.insert(ignore_permissions=True)
			doc.submit()
			print("  PO: {} — {} items, Submitted".format(supplier_name, len(po_items)))
			created.append(doc.name)
		except Exception as e:
			print("  PO: {} — Skip ({})".format(supplier_name, str(e)))

	frappe.db.commit()
	return created


# ═══════════════════════════════════════════════════════
#  8. Purchase Receipts + Batches
# ═══════════════════════════════════════════════════════

def ensure_purchase_receipts(suppliers, items, warehouses, purchase_orders):
	"""Ensure Purchase Receipts exist (with batch creation)."""
	today_dt = today()
	pr_data = [
		{
			"supplier": "Green Valley Dairy Cooperative",
			"posting_date": add_days(today_dt, -3),
			"items": [
				("Pasteurised Milk (Full Cream)", 300, "Ltr", 52.0, "CS-Chilled"),
				("Fresh Paneer (Cottage Cheese)", 100, "Kg", 280.0, "CS-Chilled"),
			],
		},
		{
			"supplier": "FreshFarm Produce Pvt Ltd",
			"posting_date": add_days(today_dt, -5),
			"items": [
				("Hybrid Tomatoes", 400, "Kg", 22.0, "CS-Chilled"),
				("Organic Bananas (Robusta)", 1500, "Nos", 8.0, "CS-Ambient"),
			],
		},
		{
			"supplier": "Himachal Apple Growers Association",
			"posting_date": add_days(today_dt, -10),
			"items": [
				("Red Delicious Apples", 200, "Kg", 120.0, "CS-Chilled"),
			],
		},
		{
			"supplier": "Coastal Fisheries Collective",
			"posting_date": add_days(today_dt, -7),
			"items": [
				("Frozen Chicken Breast", 150, "Kg", 320.0, "CS-Frozen"),
				("Frozen Green Peas", 300, "Kg", 65.0, "CS-Frozen"),
			],
		},
	]

	created_pr = []
	created_batches = []

	for pr in pr_data:
		supplier_name = pr["supplier"]
		if not frappe.db.exists("Supplier", supplier_name):
			print("  PR: Supplier {} not found, skipping".format(supplier_name))
			continue

		pr_items = []
		for item_name, qty, uom, rate, wh_key in pr["items"]:
			item_code = items.get(item_name)
			warehouse = warehouses.get(wh_key)
			if not item_code or not warehouse:
				continue
			pr_items.append({
				"item_code": item_code,
				"qty": qty,
				"uom": uom,
				"rate": rate,
				"warehouse": warehouse,
				"received_qty": qty,
			})

		if not pr_items:
			continue

		try:
			doc = frappe.get_doc({
				"doctype": "Purchase Receipt",
				"supplier": supplier_name,
				"posting_date": pr["posting_date"],
				"posting_time": "10:00:00",
				"items": pr_items,
			})
			doc.insert(ignore_permissions=True)
			doc.submit()
			print("  PR: {} — {}, {} items".format(
				doc.name, supplier_name, len(pr_items)
			))
			created_pr.append(doc.name)

			# Collect batch info from submitted PR
			for item in doc.items:
				if item.get("batch_no"):
					batch_doc = frappe.get_doc("Batch", item.batch_no)
					batch_doc.db_set("custom_grade", "A")
					batch_doc.db_set("custom_adjusted_shelf_life_days",
						frappe.db.get_value("Item", item.item_code, "shelf_life_in_days"))
					created_batches.append(item.batch_no)
					print("    Batch: {} — Grade A, shelf life set".format(item.batch_no))

		except Exception as e:
			print("  PR: {} — Skip ({})".format(supplier_name, str(e)))

	frappe.db.commit()
	return created_pr, created_batches


# ═══════════════════════════════════════════════════════
#  9. Quality Inspections
# ═══════════════════════════════════════════════════════

def ensure_quality_inspections(purchase_receipts, items):
	"""Ensure Quality Inspections linked to Purchase Receipts."""
	if not purchase_receipts:
		print("  QI: No purchase receipts to inspect")
		return []

	today_dt = today()
	inspection_data = [
		{"pr_idx": 0, "item_name": "Pasteurised Milk (Full Cream)", "moisture": 87.5, "defect": 1.0, "grade": "A"},
		{"pr_idx": 0, "item_name": "Fresh Paneer (Cottage Cheese)", "moisture": 55.0, "defect": 2.5, "grade": "A"},
		{"pr_idx": 1, "item_name": "Hybrid Tomatoes", "moisture": 93.0, "defect": 5.0, "grade": "B"},
		{"pr_idx": 1, "item_name": "Organic Bananas (Robusta)", "moisture": 74.0, "defect": 3.0, "grade": "A"},
		{"pr_idx": 2, "item_name": "Red Delicious Apples", "moisture": 84.0, "defect": 2.0, "grade": "A"},
		{"pr_idx": 3, "item_name": "Frozen Chicken Breast", "moisture": 72.0, "defect": 0.5, "grade": "A"},
		{"pr_idx": 3, "item_name": "Frozen Green Peas", "moisture": 78.0, "defect": 4.0, "grade": "B"},
	]

	created = []
	for qi in inspection_data:
		idx = qi["pr_idx"]
		if idx >= len(purchase_receipts):
			continue

		pr_name = purchase_receipts[idx]
		item_code = items.get(qi["item_name"])
		if not item_code:
			continue

		# Check if QI already exists for this PR + item
		if frappe.db.exists("Quality Inspection", {
			"reference_type": "Purchase Receipt",
			"reference_name": pr_name,
			"item_code": item_code,
		}):
			print("  QI: {} (for PR {}) — Already exists".format(qi["item_name"], pr_name))
			continue

		try:
			qi_doc = frappe.get_doc({
				"doctype": "Quality Inspection",
				"inspection_type": "Incoming",
				"reference_type": "Purchase Receipt",
				"reference_name": pr_name,
				"item_code": item_code,
				"report_date": today_dt,
				"inspected_by": "Administrator",
				"custom_moisture_percent": qi["moisture"],
				"custom_visual_defect_percent": qi["defect"],
				"custom_grade": qi["grade"],
			})
			qi_doc.insert(ignore_permissions=True)

			# Compute adjusted shelf life
			base_shelf_life = frappe.db.get_value(
				"Item", item_code, "shelf_life_in_days"
			) or 1
			multiplier = {"A": 1.0, "B": 0.7, "C": 0.4, "Reject": 0.0}
			mul = multiplier.get(qi["grade"], 1.0)
			adjusted = int(base_shelf_life * mul)
			qi_doc.db_set("custom_adjusted_shelf_life_days", adjusted)
			qi_doc.submit()

			print("  QI: {} — Grade {}, Shelf life adjusted to {} days".format(
				qi["item_name"], qi["grade"], adjusted
			))
			created.append(qi_doc.name)
		except Exception as e:
			print("  QI: {} — Skip ({})".format(qi["item_name"], str(e)))

	frappe.db.commit()
	return created


# ═══════════════════════════════════════════════════════
#  10. Stock Entries
# ═══════════════════════════════════════════════════════

def ensure_stock_entries(items, warehouses):
	"""Ensure Stock Entries for material transfers exist."""
	today_dt = today()
	se_data = [
		{
			"purpose": "Material Transfer",
			"posting_date": add_days(today_dt, -2),
			"items": [
				("Pasteurised Milk (Full Cream)", 50, "Ltr", "CS-Chilled", "CS-Transit"),
				("Fresh Paneer (Cottage Cheese)", 20, "Kg", "CS-Chilled", "CS-Transit"),
			],
		},
		{
			"purpose": "Material Transfer",
			"posting_date": add_days(today_dt, -4),
			"items": [
				("Frozen Chicken Breast", 30, "Kg", "CS-Frozen", "CS-Transit"),
				("Frozen Green Peas", 50, "Kg", "CS-Frozen", "CS-Transit"),
			],
		},
	]

	created = []
	for se in se_data:
		se_items = []
		for item_name, qty, uom, from_wh_key, to_wh_key in se["items"]:
			item_code = items.get(item_name)
			s_wh = warehouses.get(from_wh_key)
			t_wh = warehouses.get(to_wh_key)
			if not item_code or not s_wh or not t_wh:
				continue
			se_items.append({
				"item_code": item_code,
				"qty": qty,
				"uom": uom,
				"s_warehouse": s_wh,
				"t_warehouse": t_wh,
				"allow_zero_valuation_rate": 1,
			})

		if not se_items:
			continue

		try:
			doc = frappe.get_doc({
				"doctype": "Stock Entry",
				"stock_entry_type": "Material Transfer",
				"posting_date": se["posting_date"],
				"items": se_items,
			})
			doc.insert(ignore_permissions=True)
			doc.submit()
			print("  Stock Entry: {} — {} items transferred".format(
				doc.name, len(se_items)
			))
			created.append(doc.name)
		except Exception as e:
			print("  Stock Entry: {} — Skip ({})".format(
				se["purpose"], str(e)
			))

	frappe.db.commit()
	return created


# ═══════════════════════════════════════════════════════
#  11. Sales Orders
# ═══════════════════════════════════════════════════════

def ensure_sales_orders(items, warehouses):
	"""Ensure Sales Orders exist."""
	today_dt = today()
	so_data = [
		{
			"customer": "FreshMart Retail Chain",
			"delivery_date": add_days(today_dt, 3),
			"items": [
				("Pasteurised Milk (Full Cream)", 100, "Ltr", 65.0),
				("Fresh Paneer (Cottage Cheese)", 50, "Kg", 350.0),
				("Flavoured Curd (Mango)", 200, "Pkt", 45.0),
			],
		},
		{
			"customer": "SpiceJet Inflight Catering",
			"delivery_date": add_days(today_dt, 5),
			"items": [
				("Chilled Coconut Water", 500, "Ltr", 40.0),
				("Mixed Fruit Juice (Pomegranate-Apple)", 300, "Ltr", 85.0),
			],
		},
		{
			"customer": "Star Hotel & Convention Centre",
			"delivery_date": add_days(today_dt, 2),
			"items": [
				("Alphonso Mango (Hapus)", 200, "Nos", 75.0),
				("Red Delicious Apples", 50, "Kg", 180.0),
				("Farm Fresh Eggs (Tray)", 30, "Pkt", 550.0),
			],
		},
		{
			"customer": "FreshMart Retail Chain",
			"delivery_date": add_days(today_dt, 1),
			"items": [
				("Hybrid Tomatoes", 100, "Kg", 35.0),
				("Potatoes (Desi)", 200, "Kg", 22.0),
				("Organic Bananas (Robusta)", 500, "Nos", 12.0),
			],
		},
	]

	created = []
	for so in so_data:
		customer = so["customer"]
		if not frappe.db.exists("Customer", customer):
			try:
				frappe.get_doc({
					"doctype": "Customer",
					"customer_name": customer,
					"customer_group": "Commercial",
					"customer_type": "Company",
				}).insert(ignore_permissions=True)
				print("  Customer: {} — Created".format(customer))
			except Exception as e:
				print("  Customer: {} — Skip ({})".format(customer, str(e)))

		so_items = []
		for item_name, qty, uom, rate in so["items"]:
			item_code = items.get(item_name)
			if not item_code:
				continue
			so_items.append({
				"item_code": item_code,
				"qty": qty,
				"uom": uom,
				"rate": rate,
				"delivery_date": so["delivery_date"],
			})

		if not so_items:
			continue

		try:
			doc = frappe.get_doc({
				"doctype": "Sales Order",
				"customer": customer,
				"transaction_date": today_dt,
				"delivery_date": so["delivery_date"],
				"items": so_items,
			})
			doc.insert(ignore_permissions=True)
			doc.submit()
			print("  Sales Order: {} — {}, {} items".format(
				doc.name, customer, len(so_items)
			))
			created.append(doc.name)
		except Exception as e:
			print("  Sales Order: {} — Skip ({})".format(customer, str(e)))

	frappe.db.commit()
	return created


# ═══════════════════════════════════════════════════════
#  12. Delivery Notes
# ═══════════════════════════════════════════════════════

def ensure_delivery_notes(sales_orders, items, warehouses, batches):
	"""Ensure Delivery Notes for sales order deliveries."""
	today_dt = today()

	if not sales_orders:
		print("  DN: No sales orders to deliver")
		return []

	dn_data = [
		{"so_idx": 0, "posting_date": add_days(today_dt, -1)},
		{"so_idx": 3, "posting_date": today_dt},
	]

	created = []
	for dn in dn_data:
		idx = dn["so_idx"]
		if idx >= len(sales_orders):
			continue

		so_name = sales_orders[idx]
		so_doc = frappe.get_doc("Sales Order", so_name)

		dn_items = []
		for so_item in so_doc.items:
			dn_items.append({
				"item_code": so_item.item_code,
				"qty": so_item.qty,
				"uom": so_item.uom,
				"rate": so_item.rate,
				"warehouse": _pick_warehouse_for_item(so_item.item_code, warehouses),
				"against_sales_order": so_name,
				"so_detail": so_item.name,
			})

		if not dn_items:
			continue

		try:
			doc = frappe.get_doc({
				"doctype": "Delivery Note",
				"customer": so_doc.customer,
				"posting_date": dn["posting_date"],
				"items": dn_items,
				"against_sales_order": so_name,
			})
			doc.insert(ignore_permissions=True)
			doc.submit()
			print("  DN: {} — {} items delivered to {}".format(
				doc.name, len(dn_items), so_doc.customer
			))
			created.append(doc.name)
		except Exception as e:
			print("  DN: {} — Skip ({})".format(so_doc.customer, str(e)))

	frappe.db.commit()
	return created


# ═══════════════════════════════════════════════════════
#  13. Delivery Transit Logs
# ═══════════════════════════════════════════════════════

def ensure_transit_logs(delivery_notes):
	"""Ensure Delivery Transit Logs exist for outgoing deliveries."""
	if not delivery_notes:
		print("  Transit: No delivery notes to log")
		return []

	transit_data = [
		{
			"dn_idx": 0,
			"transporter": "Swift Cargo Logistics",
			"vehicle": "MH-12-AB-1234",
			"dispatch_temp": 4.5,
			"arrival_temp": 6.0,
		},
		{
			"dn_idx": 0,
			"transporter": "Rapid Chill Transport",
			"vehicle": "MH-14-XY-5678",
			"dispatch_temp": 3.8,
			"arrival_temp": 4.2,
		},
		{
			"dn_idx": 1,
			"transporter": "Swift Cargo Logistics",
			"vehicle": "MH-12-AB-5678",
			"dispatch_temp": 5.0,
			"arrival_temp": 7.5,
		},
	]

	created = []
	for t_data in transit_data:
		idx = t_data["dn_idx"]
		if idx >= len(delivery_notes):
			continue

		dn_name = delivery_notes[idx]

		if frappe.db.exists("Delivery Transit Log", {"delivery_note": dn_name}):
			print("  Transit Log: for DN {} — Already exists".format(dn_name))
			continue

		try:
			doc = frappe.get_doc({
				"doctype": "Delivery Transit Log",
				"delivery_note": dn_name,
				"transporter_name": t_data["transporter"],
				"vehicle_no": t_data["vehicle"],
				"dispatch_temp": t_data["dispatch_temp"],
				"arrival_temp": t_data["arrival_temp"],
			})
			doc.insert(ignore_permissions=True)
			# Check if arrival temp exceeds safe threshold
			breach = t_data["arrival_temp"] > 6.0
			if breach:
				doc.db_set("temperature_breach", 1)
				status = "BREACH"
			else:
				status = "OK"
			print("  Transit Log: {} → {} — {}°C > {}°C ({})".format(
				t_data["transporter"], t_data["vehicle"],
				t_data["dispatch_temp"], t_data["arrival_temp"], status
			))
			created.append(doc.name)
		except Exception as e:
			print("  Transit Log: for DN {} — Skip ({})".format(dn_name, str(e)))

	frappe.db.commit()
	return created


# ═══════════════════════════════════════════════════════
#  14. Sales Invoices
# ═══════════════════════════════════════════════════════

def _pick_warehouse_for_item(item_code, warehouses):
	"""Pick the correct warehouse based on item's storage zone."""
	if not warehouses:
		return None
	# Check item's max safe temp to determine zone
	max_temp = frappe.db.get_value("Item", item_code, "custom_max_safe_temp_c") or 25
	if max_temp <= 0:
		# Frozen items
		return warehouses.get("CS-Frozen", next(iter(warehouses.values())))
	elif max_temp <= 8:
		# Chilled items
		return warehouses.get("CS-Chilled", next(iter(warehouses.values())))
	else:
		# Ambient items
		return warehouses.get("CS-Ambient", next(iter(warehouses.values())))


def ensure_sales_invoices(sales_orders):
	"""Ensure Sales Invoices for billed sales orders."""
	today_dt = today()

	if not sales_orders:
		print("  SI: No sales orders to invoice")
		return []

	si_data = [
		{"so_idx": 0, "posting_date": add_days(today_dt, -1)},
		{"so_idx": 3, "posting_date": today_dt},
	]

	created = []
	for si in si_data:
		idx = si["so_idx"]
		if idx >= len(sales_orders):
			continue

		so_name = sales_orders[idx]
		so_doc = frappe.get_doc("Sales Order", so_name)

		si_items = []
		for so_item in so_doc.items:
			si_items.append({
				"item_code": so_item.item_code,
				"qty": so_item.qty,
				"uom": so_item.uom,
				"rate": so_item.rate,
				"sales_order": so_name,
				"so_detail": so_item.name,
			})

		if not si_items:
			continue

		try:
			doc = frappe.get_doc({
				"doctype": "Sales Invoice",
				"customer": so_doc.customer,
				"posting_date": si["posting_date"],
				"items": si_items,
			})
			doc.insert(ignore_permissions=True)
			doc.submit()
			print("  SI: {} — {} billed to {}".format(
				doc.name, len(si_items), so_doc.customer
			))
			created.append(doc.name)
		except Exception as e:
			print("  SI: {} — Skip ({})".format(so_doc.customer, str(e)))

	frappe.db.commit()
	return created


# ═══════════════════════════════════════════════════════
#  15. FEFO Override Log Entries
# ═══════════════════════════════════════════════════════

def ensure_fefo_overrides(delivery_notes, items):
	"""Create FEFO Override Notification Log entries for audit trail."""
	if not delivery_notes:
		print("  FEFO: No delivery notes for FEFO logs")
		return []

	override_data = [
		{
			"dn_idx": 0,
			"item": "Pasteurised Milk (Full Cream)",
			"selected_batch": "BATCH-003",
			"oldest_batch": "BATCH-001",
		},
		{
			"dn_idx": 0,
			"item": "Fresh Paneer (Cottage Cheese)",
			"selected_batch": "BATCH-005",
			"oldest_batch": "BATCH-002",
		},
	]

	created = []
	today_dt = nowdate()
	for od in override_data:
		idx = od["dn_idx"]
		if idx >= len(delivery_notes):
			continue

		dn_name = delivery_notes[idx]
		item_code = items.get(od["item"])

		subject = "FEFO Override — Delivery Note {}".format(dn_name)
		if frappe.db.exists("Notification Log", {"subject": ["like", "%{}%".format(subject[:40])]}):
			print("  FEFO Log: for DN {} — Already exists".format(dn_name))
			continue

		try:
			log = frappe.get_doc({
				"doctype": "Notification Log",
				"subject": subject,
				"email_content": (
					"FEFO Override Log:\n"
					"Delivery Note: {}\n"
					"Item: {}\n"
					"Selected Batch: {}\n"
					"Oldest Available Batch: {}\n"
					"Overridden By: {}\n"
					"Timestamp: {}"
				).format(dn_name, item_code or od["item"],
						 od["selected_batch"], od["oldest_batch"],
						 "Administrator", today_dt),
				"document_type": "Delivery Note",
				"document_name": dn_name,
				"for_user": "Administrator",
			})
			log.insert(ignore_permissions=True)
			print("  FEFO Log: For DN {} — Created (override of {} over {})".format(
				dn_name, od["selected_batch"], od["oldest_batch"]
			))
			created.append(log.name)
		except Exception as e:
			print("  FEFO Log: For DN {} — Skip ({})".format(dn_name, str(e)))

	frappe.db.commit()
	return created


# ═══════════════════════════════════════════════════════
#  16. Spoilage Write-Off Entry
# ═══════════════════════════════════════════════════════

def ensure_spoilage_write_off(items, warehouses, batches):
	"""Create a Material Issue Stock Entry simulating expired/spoiled stock."""
	if not batches or len(batches) < 2:
		print("  Spoilage: Not enough batches created yet")
		return None

	today_dt = today()

	# Use Spent Hen Meat which has a short shelf life (3 days)
	item_code = None
	for key, code in items.items():
		if "Spent Hen" in key:
			item_code = code
			break
	if not item_code:
		print("  Spoilage: No suitable item found for write-off")
		return None

	warehouse = None
	for k in ["CS-Chilled", "CS-Frozen", "CS-Ambient"]:
		if k in warehouses:
			warehouse = warehouses[k]
			break
	if not warehouse:
		warehouse = next(iter(warehouses.values()))

	# Find a batch for this item
	target_batch = None
	for b in batches:
		try:
			batch_doc = frappe.get_doc("Batch", b)
			if batch_doc.item == item_code:
				target_batch = b
				break
		except Exception:
			continue

	if not target_batch:
		print("  Spoilage: No matching batch for item")
		return None

	# Check if a spoilage entry already exists
	has_entry = frappe.db.exists("Stock Entry", {
		"stock_entry_type": "Material Issue",
		"posting_date": today_dt,
	})
	if has_entry:
		print("  Spoilage Entry: Already exists for today")
		return has_entry

	try:
		doc = frappe.get_doc({
			"doctype": "Stock Entry",
			"stock_entry_type": "Material Issue",
			"posting_date": today_dt,
			"items": [{
				"item_code": item_code,
				"qty": -25,
				"uom": "Kg",
				"s_warehouse": warehouse,
				"batch_no": target_batch,
				"allow_zero_valuation_rate": 1,
			}],
		})
		doc.insert(ignore_permissions=True)
		doc.submit()
		print("  Spoilage Entry: {} — 25Kg written off (Item: {})".format(
			doc.name, item_code
		))
		frappe.db.commit()
		return doc.name
	except Exception as e:
		frappe.db.rollback()
		print("  Spoilage Entry: Skip ({})".format(str(e)))
		return None
