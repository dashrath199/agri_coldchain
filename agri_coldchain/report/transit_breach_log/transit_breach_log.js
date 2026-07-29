// Copyright (c) 2025, Your Organisation and contributors
// For license information, please see license.txt

frappe.query_reports["Transit Breach Log"] = {
    filters: [
        {
            fieldname: "from_date",
            label: __("From Date"),
            fieldtype: "Date",
            default: frappe.datetime.add_months(frappe.datetime.get_today(), -3),
        },
        {
            fieldname: "to_date",
            label: __("To Date"),
            fieldtype: "Date",
            default: frappe.datetime.get_today(),
        },
        {
            fieldname: "transporter_name",
            label: __("Transporter"),
            fieldtype: "Data",
        },
    ],
    formatter: function (value, row, column, data, default_formatter) {
        value = default_formatter(value, row, column, data);

        if (column.fieldname === "arrival_temp" && data) {
            if (data.arrival_temp > 10) {
                value = `<span style="color:#e74c3c;font-weight:bold;">${value}°C 🚨</span>`;
            } else if (data.arrival_temp > 4) {
                value = `<span style="color:#e67e22;font-weight:bold;">${value}°C ⚠</span>`;
            }
        }

        return value;
    },
};
