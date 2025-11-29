
import frappe

@frappe.whitelist()
@frappe.validate_and_sanitize_search_inputs
def get_closed_won_customers_query(doctype, txt, searchfield, start, page_len, filters):
    return frappe.db.sql("""
        SELECT 
            DISTINCT `tabCustomer`.name, `tabCustomer`.customer_name
        FROM 
            `tabCustomer`
        JOIN 
            `tabOpportunity` ON `tabOpportunity`.customer_name = `tabCustomer`.customer_name
        WHERE 
            `tabCustomer`.custom_vertical IN ('Temporary Staffing', 'Permanent Staffing')
            AND `tabOpportunity`.status = 'Closed Won'
            AND `tabCustomer`.name LIKE %(txt)s
        ORDER BY 
            `tabCustomer`.name ASC
        LIMIT %(start)s, %(page_len)s
    """, {
        'txt': "%%%s%%" % txt,
        'start': start,
        'page_len': page_len
    })