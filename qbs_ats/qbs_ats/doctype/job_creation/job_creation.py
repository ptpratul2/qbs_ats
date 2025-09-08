

import frappe
from frappe.model.document import Document
import requests
import time
from datetime import datetime, timedelta
from requests.adapters import HTTPAdapter
from requests.packages.urllib3.util.retry import Retry

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
        response = requests.post(url, json=payload, headers=headers, timeout=60)
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

    if not token or not expiry_str:
        return generate_ceipal_token().get("access_token")

    try:
        expiry_time = datetime.fromisoformat(expiry_str)
        if expiry_time < datetime.now():
            return generate_ceipal_token().get("access_token")
    except Exception:
        return generate_ceipal_token().get("access_token")

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


# 🔹 Background Job Trigger
@frappe.whitelist()
def enqueue_job_sync(batch_size=50, start_page=1, max_pages=None):
    """Run job sync in background queue to avoid timeout"""
    frappe.enqueue(
        "qbs_ats.qbs_ats.doctype.job_creation.job_creation.custom_method",
        batch_size=batch_size,
        start_page=start_page,
        max_pages=max_pages,
        queue="long",
        timeout=3600
    )
    return {"status": "queued", "message": "Job Sync has been enqueued in background."}


@frappe.whitelist()
def custom_method(batch_size=50, start_page=1, max_pages=None):
    frappe.logger().info("Starting CEIPAL → ERPNext Job Sync (Batch Mode)")

    token = get_active_token()
    if not token:
        return {"status": "error", "message": "Failed to generate CEIPAL token."}

    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    session = requests_session()

    created_count, skipped_count, errors_count = 0, 0, 0
    page, has_more = start_page, True

    while has_more:
        if max_pages and page > max_pages:
            break

        next_page_url = f"{CEIPAL_API_URL}page={page}&limit={batch_size}"
        frappe.logger().info(f"Fetching jobs from: {next_page_url}")

        try:
            response = session.get(next_page_url, headers=headers, timeout=300)
            if response.status_code in [401, 403]:
                token = generate_ceipal_token().get("access_token")
                headers["Authorization"] = f"Bearer {token}"
                response = session.get(next_page_url, headers=headers, timeout=300)

            response.raise_for_status()
            data = response.json()

        except requests.exceptions.Timeout:
            frappe.logger().info(f"Timeout fetching {next_page_url}, skipping...")
            errors_count += 1
            page += 1
            continue
        except Exception as e:
            frappe.log_error(f"Request failed: {str(e)}", "CEIPAL Job Sync")
            break

        jobs_from_api = data.get("results", [])
        if not jobs_from_api:
            has_more = False
            break

        for job_data in jobs_from_api:
            try:
                res = sync_erpnext_document(job_data)
                if res and res["status"] == "created":
                    created_count += 1
                elif res and res["status"] == "skipped":
                    skipped_count += 1
            except Exception as e:
                frappe.log_error(f"Job sync failed: {str(e)}", "CEIPAL Job Sync")
                errors_count += 1

        frappe.db.commit()
        time.sleep(1)
        page += 1

    success_message = f"Job Sync Completed → Created: {created_count}, Skipped: {skipped_count}, Errors: {errors_count}"
    frappe.logger().info(success_message)
    return {"status": "success", "message": success_message}


def sync_erpnext_document(job_data):
    ceipal_unique_id = job_data.get("id")
    if not ceipal_unique_id:
        return {"status": "skipped"}

    try:
        existing_doc = frappe.get_value(
            ERPNEXT_DOCTYPE, {"ceipal_ref": ceipal_unique_id}, "name"
        )
        if existing_doc:
            return {"status": "skipped"}  # 🚀 Skip already existing job

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
            "job_description": job_data.get("public_job_desc")
                               or job_data.get("requisition_description")
                               or "",
            "remote_job": job_data.get("remote_opportunities", ""),
            "post_job_on_career_portal": 1 if str(job_data.get("post_on_careerportal", "")).lower() in ["1", "yes", "true"] else 0,
        }

        doc = frappe.new_doc(ERPNEXT_DOCTYPE)
        doc.update(data_to_sync)
        doc.insert(ignore_permissions=True)
        doc.submit()

        return {"status": "created", "doc_name": doc.name}

    except Exception as e:
        frappe.log_error(f"Error syncing job {ceipal_unique_id}: {e}", "CEIPAL Job Sync Error")
        return {"status": "error"}
