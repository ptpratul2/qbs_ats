import frappe


@frappe.whitelist()
def get_cv_stats(job_name):
    
    if not job_name:
        return {}

    query = """
        SELECT 
            child.owner as user, COUNT(child.name) as count
        FROM 
            `tabPDF Upload File` child
        INNER JOIN 
            `tabPDF Upload` parent ON child.parent = parent.name
        WHERE 
            parent.job_title = %s
            AND child.parenttype = 'PDF Upload'
        GROUP BY 
            child.owner
    """
    
    try:
        data = frappe.db.sql(query, (job_name), as_dict=True)
        result = { d.user: d.count for d in data }
        return result
    except Exception as e:
        frappe.log_error(message=frappe.get_traceback(), title="CV Count API Error")
        return {}