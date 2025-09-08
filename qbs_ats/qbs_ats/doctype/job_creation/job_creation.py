

import frappe
from frappe.model.document import Document
import requests
import time
from datetime import datetime, timedelta
from requests.adapters import HTTPAdapter
from requests.packages.urllib3.util.retry import Retry

# CEIPAL API Endpoints
CEIPAL_API_URL = "https://api.ceipal.com/v1/getJobPostingsList?"
CEIPAL_AUTH_URL = "https://api.ceipal.com/v1/createAuthtoken"

ERPNEXT_DOCTYPE = "Job Creation"


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


# 🔹 Active Token Manager
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


# 🔹 Request Session with Retry
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


# 🔹 Main Sync Method
@frappe.whitelist()
def custom_method(batch_size=50, start_page=1, max_pages=None):
    frappe.msgprint("Starting CEIPAL → ERPNext Job Sync (Batch Mode)")
    print("Starting CEIPAL Job Sync...")

    token = get_active_token()
    if not token:
        token_data = generate_ceipal_token()
        if not token_data or not token_data.get("access_token"):
            message = "Failed to generate CEIPAL token. Sync stopped."
            frappe.log_error(message, "CEIPAL Job Sync")
            return {"status": "error", "message": message}
        token = token_data.get("access_token")

    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    session = requests_session()

    created_count, updated_count, errors_count = 0, 0, 0
    page, has_more = start_page, True

    while has_more:
        if max_pages and page > max_pages:
            print(f"Reached max_pages limit: {max_pages}")
            break

        next_page_url = f"{CEIPAL_API_URL}page={page}&limit={batch_size}"
        print(f"Fetching jobs from: {next_page_url}")

        try:
            response = session.get(next_page_url, headers=headers, timeout=90)

            # Token expired → regenerate
            if response.status_code in [401, 403]:
                token_data = generate_ceipal_token()
                if not token_data or not token_data.get("access_token"):
                    message = f"Token error ({response.status_code}). Regeneration failed."
                    frappe.log_error(message, "CEIPAL Job Sync")
                    return {"status": "error", "message": message}
                token = token_data.get("access_token")
                headers["Authorization"] = f"Bearer {token}"
                response = session.get(next_page_url, headers=headers, timeout=90)

            response.raise_for_status()
            data = response.json()

        except requests.exceptions.Timeout:
            frappe.logger().info(f"Timeout fetching: {next_page_url}, retrying after 5s...")
            time.sleep(5)
            continue
        except Exception as e:
            frappe.log_error(f"Request failed for {next_page_url}: {str(e)}", "CEIPAL Job Sync")
            break

        jobs_from_api = data.get("results", [])
        print(f"Page {page}: received {len(jobs_from_api)} jobs")

        if not jobs_from_api:
            has_more = False
            break

        # Process in batches
        for i in range(0, len(jobs_from_api), batch_size):
            batch = jobs_from_api[i:i + batch_size]
            print(f"Processing batch {i//batch_size + 1} (size {len(batch)}) from page {page}")

            for job_data in batch:
                try:
                    res = sync_erpnext_document(job_data)
                    if res and res["status"] == "created":
                        created_count += 1
                    elif res and res["status"] == "updated":
                        updated_count += 1
                    else:
                        errors_count += 1
                except Exception as e:
                    frappe.log_error(f"Job sync failed: {str(e)}", "CEIPAL Job Sync")
                    errors_count += 1

            frappe.db.commit()
            time.sleep(1)

        if data.get("next"):
            page += 1
        else:
            has_more = False

    success_message = f"Job Sync completed. Created: {created_count}, Updated: {updated_count}, Failed: {errors_count}."
    print(success_message)
    return {"status": "success", "message": success_message, "created": created_count, "updated": updated_count, "failed": errors_count}


# 🔹 Sync Job to ERPNext
def sync_erpnext_document(job_data):
    ceipal_unique_id = job_data.get("id")
    if not ceipal_unique_id:
        return None

    try:
        existing_docs = frappe.get_list(
            ERPNEXT_DOCTYPE,
            filters={"ceipal_ref": ceipal_unique_id},
            fields=["name", "docstatus"]
        )
        existing_doc_name = existing_docs[0]["name"] if existing_docs else None
        existing_doc_status = existing_docs[0]["docstatus"] if existing_docs else 0

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
            "apply_job": job_data.get("apply_job", ""),
            "job_category": job_data.get("job_category", ""),
            "apply_job_without_registration": job_data.get("apply_job_without_registration", ""),
            "tax_terms": job_data.get("tax_terms", ""),
            "job_description": job_data.get("public_job_desc") or job_data.get("requisition_description") or "",
            "remote_job": job_data.get("remote_opportunities", ""),
            "post_job_on_career_portal": 1 if str(job_data.get("post_on_careerportal", "")).lower() in ["1", "yes", "true"] else 0,
        }

        if existing_doc_status == 0:
            data_to_sync["updated"] = job_data.get("updated", "")

        # Clean empty strings
        for key, value in data_to_sync.items():
            if isinstance(value, str) and not value.strip():
                data_to_sync[key] = None

        if existing_doc_name:
            doc = frappe.get_doc(ERPNEXT_DOCTYPE, existing_doc_name)
            doc.update(data_to_sync)
            doc.save(ignore_permissions=True)
            if doc.docstatus == 0:  
                doc.submit()
            return {"status": "updated", "doc_name": doc.name}
        else:
            doc = frappe.new_doc(ERPNEXT_DOCTYPE)
            doc.update(data_to_sync)
            doc.insert(ignore_permissions=True)
            doc.submit()
            return {"status": "created", "doc_name": doc.name}

    except Exception as e:
        frappe.log_error(f"Error syncing job {ceipal_unique_id}: {e}", "CEIPAL Job Sync Error")
        return None
