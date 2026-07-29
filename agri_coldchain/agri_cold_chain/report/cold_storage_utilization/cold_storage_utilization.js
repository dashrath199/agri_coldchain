// Copyright (c) 2025, Your Organisation and contributors
// For license information, please see license.txt

frappe.query_reports["Cold Storage Utilization"] = {
    filters: [
        {
            fieldname: "zone_type",
            label: __("Zone Type"),
            fieldtype: "Select",
            options: ["", "Frozen", "Chilled", "Ambient"],
        },
    ],
    formatter: function (value, row, column, data, default_formatter) {
        value = default_formatter(value, row, column, data);

        if (column.fieldname === "utilization_pct" && data) {
            if (data.utilization_pct >= 90) {
                value = `<span style="color:white;background:#e74c3c;padding:2px 8px;border-radius:10px;">${value}%</span>`;
            } else if (data.utilization_pct >= 75) {
                value = `<span style="color:white;background:#e67e22;padding:2px 8px;border-radius:10px;">${value}%</span>`;
            } else {
                value = `<span style="color:white;background:#27ae60;padding:2px 8px;border-radius:10px;">${value}%</span>`;
            }
        }

        return value;
    },
};
