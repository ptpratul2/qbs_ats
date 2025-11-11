import frappe
from frappe.model.document import Document
import requests
import time
from datetime import datetime, timedelta
from requests.adapters import HTTPAdapter
from requests.packages.urllib3.util.retry import Retry

CEIPAL_AUTH_URL = "https://api.ceipal.com/v1/createAuthtoken"
CEIPAL_LIST_URL = "https://api.ceipal.com/v1/getJobPostingsList?"
CEIPAL_DETAIL_URL = "https://api.ceipal.com/v1/getJobPostingDetails/?job_id="

ERPNEXT_DOCTYPE = "Job Creation"
ERPNEXT_CHILD_DOCTYPE = "Pay Rates"

class JobCreation(Document):
    pass

def requests_session():
    session = requests.Session()
    retries = Retry(
        total=5,
        backoff_factor=3,
        status_forcelist=[403, 429, 500, 502, 503, 504],
        allowed_methods=["GET", "POST"]
    )
    adapter = HTTPAdapter(max_retries=retries)
    session.mount("http://", adapter)
    session.mount("https://", adapter)
    return session

@frappe.whitelist()
def generate_ceipal_token():
    payload = {
        "email": "nidhi@promptpersonnel.com",
        "password": "Ceipal@123",
        "api_key": "b6a7e8fef13019e45a587c486d0a9718ebfc6a256acdeec50f67308c1a1856b3"
    }
    headers = {"Content-Type": "application/json", "Accept": "application/json"}
    try:
        response = requests.post(CEIPAL_AUTH_URL, json=payload, headers=headers, timeout=60)
        response.raise_for_status()
        data = response.json()
        access_token = data.get("access_token")
        expiry = (datetime.now() + timedelta(minutes=55)).isoformat()
        frappe.db.set_default("ceipal_access_token", access_token)
        frappe.db.set_default("ceipal_token_expiry", expiry)
        frappe.db.commit()
        return {"status": "success", "access_token": access_token}
    except Exception as e:
        frappe.log_error(f"CEIPAL Token Error: {str(e)[:140]}", "CEIPAL Auth Error")
        return {"status": "error", "message": str(e)}

def get_active_token():
    token = frappe.db.get_default("ceipal_access_token")
    expiry_str = frappe.db.get_default("ceipal_token_expiry")
    if not token or not expiry_str:
        return generate_ceipal_token().get("access_token")
    try:
        expiry_time = datetime.fromisoformat(expiry_str)
        if expiry_time < datetime.now():
            return generate_ceipal_token().get("access_token")
    except Exception:
        return generate_ceipal_token().get("access_token")
    return token

# ------------------------
# Background enqueue function
# ------------------------
@frappe.whitelist()
def custom_method(batch_size=50, start_page=1, max_pages=None):
    frappe.enqueue(
        "qbs_ats.qbs_ats.doctype.job_creation.job_creation.sync_jobs_in_background",
        batch_size=batch_size,
        start_page=start_page,
        max_pages=max_pages,
        queue="long",
        timeout=3600
    )
    return {"status": "queued", "message": "Job Sync start"}

@frappe.whitelist()
def sync_jobs_in_background(batch_size=50, start_page=1, max_pages=None):
    token = get_active_token()
    if not token:
        return {"status": "error", "message": "Failed to get token"}

    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    session = requests_session()
    page = start_page
    created_count = updated_count = skipped_count = errors_count = 0
    has_more = True

    while has_more:
        if max_pages and page > max_pages:
            break

        try:
            list_response = session.get(f"{CEIPAL_LIST_URL}page={page}&limit={batch_size}", headers=headers, timeout=120)
            if list_response.status_code in [401, 403]:
                token = generate_ceipal_token().get("access_token")
                headers["Authorization"] = f"Bearer {token}"
                list_response = session.get(f"{CEIPAL_LIST_URL}page={page}&limit={batch_size}", headers=headers, timeout=120)
            list_response.raise_for_status()
            jobs = list_response.json().get("results", [])
        except Exception as e:
            frappe.log_error(f"Job List API failed: {str(e)[:140]}", "CEIPAL Job List Error")
            break

        if not jobs:
            break

        for job_summary in jobs:
            job_id = job_summary.get("id")
            if not job_id:
                skipped_count += 1
                continue
            try:
                detail_response = session.get(f"{CEIPAL_DETAIL_URL}{job_id}", headers=headers, timeout=120)
                detail_response.raise_for_status()
                job_detail_data = detail_response.json()
                status, _ = create_or_update_erpnext_job(job_detail_data)
                if status == "created": created_count += 1
                elif status == "updated": updated_count += 1
                elif status == "skipped": skipped_count += 1
                else: errors_count += 1
            except Exception as e:
                frappe.log_error(f"Job Detail API failed for {job_id}: {str(e)[:140]}", "CEIPAL Job Detail Error")
                errors_count += 1
            time.sleep(1)

        frappe.db.commit()
        page += 1

    return {"status": "success", "message": f"Sync Completed: Created {created_count}, Updated {updated_count}, Skipped {skipped_count}, Errors {errors_count}"}

# ------------------------
# Job create/update function
# ------------------------
def create_or_update_erpnext_job(job_data):
    ceipal_id = job_data.get("id")
    if not ceipal_id: return "error", None

    existing_doc_name = frappe.get_value(ERPNEXT_DOCTYPE, {"ceipal_ref": ceipal_id}, "name")
    if existing_doc_name:
        doc = frappe.get_doc(ERPNEXT_DOCTYPE, existing_doc_name)
        status = "updated"
        if doc.docstatus == 1:
            try: doc.cancel()
            except: return "skipped", doc.name
    else:
        doc = frappe.new_doc(ERPNEXT_DOCTYPE)
        doc.ceipal_ref = ceipal_id
        status = "created"

    def safe_int(val):
        try: return int(val)
        except: return None

    doc.update({
        "job_code": job_data.get("job_code",""),
        "job_title": job_data.get("position_title",""),
        "job_status": job_data.get("job_status",""),
        "job_type": job_data.get("employment_type",""),
        "country": job_data.get("country",""),
        "states": job_data.get("state",""),
        "job_start_date": job_data.get("job_start_date",""),
        "job_end_date": job_data.get("job_end_date",""),
        "priority": job_data.get("priority",""),
        "skills": job_data.get("skills",""),
        "postal_code": job_data.get("postal_code",""),
        "updated": job_data.get("modified",""),
        "work_authorization": job_data.get("work_authorization",""),
        "industry": job_data.get("industry",""),
        "job_description": job_data.get("public_job_desc") or job_data.get("requisition_description") or "",
        "remote_job": job_data.get("remote_opportunities",""),
        "post_job_on_career_portal": 1 if str(job_data.get("post_on_careerportal","")).lower() in ["1","yes","true"] else 0,
        "business_unit_id": job_data.get("business_unit_id",""),
        "created": job_data.get("created",""),
        "experience": job_data.get("experience",""),
        "min_experience": job_data.get("min_experience",""),
        "number_of_positions": job_data.get("number_of_positions",""),
        "hours": safe_int(job_data.get("hours","")),
        "department": job_data.get("department",""),
        "posted": job_data.get("posted",""),
        "apply_job": job_data.get("apply_job","")
    })

    doc.set("pay_rates", [])
    for pr in job_data.get("pay_rates", []):
        doc.append("pay_rates", {
            "pay_rate_currency": pr.get("pay_rate_currency",""),
            "pay_rate": pr.get("pay_rate",""),
            "pay_rate_pay_frequency_type": pr.get("pay_rate_pay_frequency_type",""),
            "min_pay_rate": pr.get("min_pay_rate",""),
            "max_pay_rate": pr.get("max_pay_rate",""),
            "pay_rate_employment_type": pr.get("pay_rate_employment_type","")
        })

    try:
        if status == "created":
            doc.insert(ignore_permissions=True)
            doc.submit()
        else:
            doc.save(ignore_permissions=True)
            if doc.docstatus == 1: doc.submit()
        frappe.db.commit()
        return status, doc.name
    except Exception as e:
        frappe.log_error(f"Error saving Job {ceipal_id}: {str(e)[:140]}", "ERPNext Sync Error")
        frappe.db.rollback()
        return "error", None




@frappe.whitelist()
def get_submissions_for_job(job_id):
    """
    Job Creation ke liye Applicants data fetch karega
    """
    try:
        submissions = frappe.get_all(
            "Applicants",
            filters={"job_title": job_title},
            fields=["name", "data_css", "applicant_status", "creation"],
            order_by="creation desc"
        )
        return submissions
    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "Error in get_submissions_for_job")
        return []
