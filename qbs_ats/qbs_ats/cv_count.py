import frappe



@frappe.whitelist()
def get_cv_stats(job_name):

    if not job_name:
        return {}

    try:
        data = frappe.db.sql("""
            SELECT 
                custom__recruiter AS user,
                COUNT(name) AS count
            FROM 
                `tabJob Applicant`
            WHERE 
                job_title = %s
                AND IFNULL(custom__recruiter, '') != ''
            GROUP BY 
                custom__recruiter
        """, (job_name,), as_dict=True)

        # Convert to dict → {user: count}
        return {d["user"]: d["count"] for d in data}

    except Exception:
        frappe.log_error(
            message=frappe.get_traceback(),
            title="CV Count API Error"
        )
        return {}