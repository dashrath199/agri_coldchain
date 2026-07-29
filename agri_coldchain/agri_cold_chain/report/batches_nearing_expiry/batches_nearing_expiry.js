// Copyright (c) 2025, Your Organisation and contributors
// For license information, please see license.txt

frappe.query_reports["Batches Nearing Expiry"] = {
    filters: [
        {
            fieldname: "item_code",
            label: __("Item"),
            fieldtype: "Link",
            options: "Item",
        },
        {
            fieldname: "warehouse",
            label: __("Warehouse"),
            fieldtype: "Link",
            options: "Warehouse",
        },
        {
            fieldname: "batch_no",
            label: __("Batch No"),
            fieldtype: "Data",
        },
        {
            fieldname: "min_risk_pct",
            label: __("Min Risk (%)"),
            fieldtype: "Percent",
            default: 70,
        },
    ],
    formatter: function (value, row, column, data, default_formatter) {
        value = default_formatter(value, row, column, data);

        if (column.fieldname === "risk_pct" && data) {
            if (data.risk_pct >= 90) {
                value = `<span style="color:white;background:#e74c3c;padding:2px 8px;border-radius:10px;">${value}</span>`;
            } else if (data.risk_pct >= 80) {
                value = `<span style="color:white;background:#e67e22;padding:2px 8px;border-radius:10px;">${value}</span>`;
            } else {
                value = `<span style="color:white;background:#f39c12;padding:2px 8px;border-radius:10px;">${value}</span>`;
            }
        }

        return value;
    },
};
