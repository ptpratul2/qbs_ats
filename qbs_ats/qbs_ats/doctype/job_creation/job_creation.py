import frappe
from frappe.model.document import Document
import requests
import json
from datetime import datetime, timedelta
import time
from requests.adapters import HTTPAdapter
from requests.packages.urllib3.util.retry import Retry

# CEIPAL API Endpoints
CEIPAL_API_URL = "https://api.ceipal.com/v1/getJobPostingsList?"
CEIPAL_AUTH_URL = "https://api.ceipal.com/v1/createAuthtoken"  

ERPNEXT_URL = frappe.utils.get_url()
ERPNEXT_DOCTYPE = "Job Creation"
ERPNEXT_API_KEY = "2a2fc1ab06c9488"  
ERPNEXT_API_SECRET = "b31a26cef0d09c8"  


class JobCreation(Document):
    pass


@frappe.whitelist()
def generate_ceipal_token():
    url = CEIPAL_AUTH_URL
    payload = {
        "email": "nidhi@promptpersonnel.com",
        "password": "Ceipal@123",
        "api_key": "b6a7e8fef13019e45a587c486d0a9718ebfc6a256acdeec50f67308c1a1856b3"
    }
    headers = {"Content-Type": "application/json", "Accept": "application/json"}

    try:
        response = requests.post(url, json=payload, headers=headers, timeout=30)
        response.raise_for_status()
        data = response.json()

        access_token = data.get("access_token")
        refresh_token = data.get("refresh_token")
        expiry = (datetime.now() + timedelta(minutes=55)).isoformat()

        frappe.db.set_default("ceipal_access_token", access_token)
        frappe.db.set_default("ceipal_refresh_token", refresh_token)
        frappe.db.set_default("ceipal_token_expiry", expiry)
        frappe.db.commit()

        frappe.logger().info(f"New CEIPAL Token Generated: {access_token[:10]}...")
        return {"status": "success", "access_token": access_token}

    except Exception as e:
        frappe.log_error(f"CEIPAL Token Generation Error: {str(e)}", "CEIPAL Auth Error")
        return {"status": "error", "message": str(e)}


def get_active_token():
    token = frappe.db.get_default("ceipal_access_token")
    expiry_str = frappe.db.get_default("ceipal_token_expiry")
    
    current_time = datetime.now()
    token_expired = False

    if expiry_str:
        try:
            expiry_time = datetime.fromisoformat(expiry_str)
            if expiry_time < current_time:
                token_expired = True
        except Exception:
            token_expired = True

    if not token or not expiry_str or token_expired:
        frappe.logger().info("Token expired/missing → regenerating")
        token_resp = generate_ceipal_token()
        if token_resp.get("status") == "success":
            return token_resp.get("access_token")
        else:
            return None
    return token


def get_ceipal_job_postings(batch_size=50, max_pages=100):
    """Fetch jobs from Ceipal in batches with retry + timeout handling"""
    all_job_postings = []
    current_page_url = f"{CEIPAL_API_URL}limit={batch_size}"
    page_count = 0

    # Session with retry
    session = requests.Session()
    retries = Retry(
        total=3,
        backoff_factor=2,
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=["GET", "POST"]
    )
    session.mount("https://", HTTPAdapter(max_retries=retries))

    while current_page_url and page_count < max_pages:
        page_count += 1
        token = get_active_token()
        if not token:
            frappe.log_error("No CEIPAL token available", "CEIPAL API Error")
            return all_job_postings

        headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

        try:
            frappe.logger().info(f"Fetching jobs batch {page_count}: {current_page_url}")
            response = session.get(current_page_url, headers=headers, timeout=30)

            if response.status_code == 401:  # token expired
                frappe.logger().info("Token rejected (401) → regenerating...")
                token_resp = generate_ceipal_token()
                if token_resp.get("status") == "success":
                    token = token_resp.get("access_token")
                    headers["Authorization"] = f"Bearer {token}"
                    response = session.get(current_page_url, headers=headers, timeout=30)
                else:
                    frappe.log_error("Failed to regenerate token after 401", "CEIPAL API Error")
                    return all_job_postings

            response.raise_for_status()
            api_response = response.json()

            jobs_on_page = api_response.get("results", [])
            if jobs_on_page:
                all_job_postings.extend(jobs_on_page)
                frappe.logger().info(f"Batch {page_count}: fetched {len(jobs_on_page)} jobs (total {len(all_job_postings)})")
            else:
                break

            current_page_url = api_response.get("next")
            if not current_page_url:
                break

            time.sleep(2)  

        except Exception as e:
            frappe.log_error(f"Error fetching data (Batch {page_count}): {e}", "CEIPAL API Error")
            break

    return all_job_postings


@frappe.whitelist()
def custom_method(batch_size=50):
    frappe.msgprint("Starting Ceipal → ERPNext Job Sync (Batch Mode)")
    job_postings = get_ceipal_job_postings(batch_size=batch_size)

    frappe.logger().info(f"Total Jobs Fetched: {len(job_postings)}")
    if not job_postings:
        return "No job postings found from Ceipal API."

    synced_count = 0
    errors_count = 0

    for i in range(0, len(job_postings), batch_size):
        batch = job_postings[i:i + batch_size]
        frappe.logger().info(f"Syncing batch {i//batch_size + 1}, size {len(batch)}")

        for job in batch:
            res = sync_erpnext_document(job)
            if res:
                synced_count += 1
            else:
                errors_count += 1

        frappe.db.commit()  
        time.sleep(1)       

    return f"Ceipal Job Sync Complete! Synced: {synced_count}, Failed: {errors_count}"


def sync_erpnext_document(job_data):
    ceipal_unique_id = job_data.get("id")
    if not ceipal_unique_id:
        return None

    try:
        existing_docs = frappe.get_list(ERPNEXT_DOCTYPE,
                                        filters={"ceipal_ref": ceipal_unique_id},
                                        fields=["name"])
        existing_doc_name = existing_docs[0]["name"] if existing_docs else None

        data_to_sync = {
            "ceipal_ref": ceipal_unique_id,
            "job_title": job_data.get("position_title", ""),
            "job_code": job_data.get("job_code", ""),
            "job_status": job_data.get("job_status", ""),
            "job_type": job_data.get("job_type", ""),
            "country": job_data.get("country", ""),
            "states": job_data.get("state", ""),
            "job_start_date": job_data.get("job_start_date", ""),
            "job_end_date": job_data.get("job_end_date", ""),
            "priority": job_data.get("priority", ""),
            "skills": job_data.get("skills", ""),
            "postal_code": job_data.get("postal_code", ""),
            "updated": job_data.get("updated", ""),
            "apply_job": job_data.get("apply_job", ""),
            "job_category": job_data.get("job_category", ""),
            "apply_job_without_registration": job_data.get("apply_job_without_registration", ""),
            "tax_terms": job_data.get("tax_terms", ""),
            "job_description": job_data.get("public_job_desc") or job_data.get("requisition_description") or "",
            "remote_job": job_data.get("remote_opportunities", ""),
            "post_job_on_career_portal": 1 if str(job_data.get("post_on_careerportal", "")).lower() in ["1", "yes", "true"] else 0,
        }

        for key, value in data_to_sync.items():
            if isinstance(value, str) and not value.strip():
                data_to_sync[key] = None

        if existing_doc_name:
            doc = frappe.get_doc(ERPNEXT_DOCTYPE, existing_doc_name)
            doc.update(data_to_sync)
            doc.save(ignore_permissions=True)
            doc.submit()
            return {"status": "updated", "doc_name": doc.name}
        else:
            doc = frappe.new_doc(ERPNEXT_DOCTYPE)
            doc.update(data_to_sync)
            doc.insert(ignore_permissions=True)
            doc.submit()
            return {"status": "created", "doc_name": doc.name}

    except Exception as e:
        frappe.log_error(f"Error syncing job {ceipal_unique_id}: {e}", "CEIPAL Sync Error")
        return None
