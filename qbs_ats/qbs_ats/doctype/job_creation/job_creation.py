import frappe
from frappe.model.document import Document
import requests
import json
from datetime import datetime, timedelta
import time  # Import time for adding delays if needed

# CEIPAL API Endpoints
CEIPAL_API_URL = "https://api.ceipal.com/v1/getJobPostingsList?"
CEIPAL_AUTH_URL = "https://api.ceipal.com/v1/createAuthtoken"  

ERPNEXT_URL = frappe.utils.get_url()
ERPNEXT_DOCTYPE = "Job Creation"
ERPNEXT_API_KEY = "2a2fc1ab06c9488"  # Use frappe.get_site_config for sensitive info
ERPNEXT_API_SECRET = "b31a26cef0d09c8"  # Use frappe.get_site_config for sensitive info


class JobCreation(Document):
    pass


# ------------------ TOKEN HANDLING ------------------
@frappe.whitelist()
def generate_ceipal_token():
    """
    Generate CEIPAL Access Token using API and save in tabSingles
    """
    url = CEIPAL_AUTH_URL
    payload = {
        "email": "nidhi@promptpersonnel.com",  # Consider fetching from site_config or DocType
        "password": "Ceipal@123",              # Consider fetching from site_config or DocType
        "api_key": "b6a7e8fef13019e45a587c486d0a9718ebfc6a256acdeec50f67308c1a1856b3"  # Consider fetching from site_config or DocType
    }
    headers = {"Content-Type": "application/json", "Accept": "application/json"}

    try:
        response = requests.post(url, json=payload, headers=headers, timeout=30)  # Added timeout
        response.raise_for_status()
        data = response.json()

        access_token = data.get("access_token")
        refresh_token = data.get("refresh_token")
        # Token typically expires in 1 hour. Give it a small buffer.
        expiry = (datetime.now() + timedelta(minutes=55)).isoformat()

        frappe.db.set_default("ceipal_access_token", access_token)
        frappe.db.set_default("ceipal_refresh_token", refresh_token)
        frappe.db.set_default("ceipal_token_expiry", expiry)
        frappe.db.commit()  # Commit the defaults to ensure they are saved immediately

        print("New CEIPAL Token Generated:", access_token[:10] + "...")
        frappe.logger().info(f"New CEIPAL Token Generated: {access_token[:10]}...")
        return {"status": "success", "access_token": access_token}

    except requests.exceptions.RequestException as e:
        frappe.log_error(f"CEIPAL Token Generation Request Error: {str(e)}", "CEIPAL Auth Error")
        print("Error while generating CEIPAL token (Request):", str(e))
        return {"status": "error", "message": f"Request Error: {str(e)}"}
    except Exception as e:
        frappe.log_error(f"CEIPAL Token Generation General Error: {str(e)}", "CEIPAL Auth Error")
        print("Error while generating CEIPAL token (General):", str(e))
        return {"status": "error", "message": f"General Error: {str(e)}"}


def get_active_token():
    """Fetch token from DB. If expired/missing, regenerate."""
    token = frappe.db.get_default("ceipal_access_token")
    expiry_str = frappe.db.get_default("ceipal_token_expiry")
    
    current_time = datetime.now()
    token_expired = False

    if expiry_str:
        try:
            expiry_time = datetime.fromisoformat(expiry_str)
            if expiry_time < current_time:
                token_expired = True
        except ValueError:
            frappe.log_error("Invalid CEIPAL token expiry format in DB", "CEIPAL Token Check")
            token_expired = True

    if not token or not expiry_str or token_expired:
        frappe.logger().info("CEIPAL Token Expired/Missing/Invalid → Generating new token")
        print("CEIPAL Token Expired/Missing/Invalid → Generating new token...")
        token_resp = generate_ceipal_token()
        if token_resp.get("status") == "success":
            return token_resp.get("access_token")
        else:
            frappe.log_error("Failed to generate new CEIPAL token during get_active_token", "CEIPAL Token Error")
            return None
    return token


# ------------------ JOB FETCHING ------------------
def get_ceipal_job_postings():
    """Fetch ALL jobs from Ceipal using pagination and latest token."""
    all_job_postings = []
    current_page_url = CEIPAL_API_URL

    while current_page_url:
        token = get_active_token()
        if not token:
            frappe.log_error("No CEIPAL token available for fetching jobs", "CEIPAL API Error")
            print("No CEIPAL token available for fetching jobs")
            return []

        headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

        try:
            print(f"Fetching jobs from URL: {current_page_url}")
            response = requests.get(current_page_url, headers=headers, timeout=120)

            if response.status_code == 401:
                frappe.logger().info("Token explicitly rejected (401) during job fetch → Regenerating and retrying...")
                print("Token explicitly rejected (401) during job fetch → Regenerating and retrying...")
                token_resp = generate_ceipal_token()
                if token_resp.get("status") == "success":
                    token = token_resp.get("access_token")
                    headers["Authorization"] = f"Bearer {token}"
                    response = requests.get(current_page_url, headers=headers, timeout=120)
                else:
                    frappe.log_error("Failed to regenerate token after 401 during job fetch. Sync stopped.", "CEIPAL API Error")
                    print("Failed to regenerate token after 401 during job fetch. Sync stopped.")
                    return []

            response.raise_for_status()
            api_response = response.json()

            jobs_on_page = api_response.get("results", [])
            if jobs_on_page:
                all_job_postings.extend(jobs_on_page)
                print(f"Fetched {len(jobs_on_page)} jobs from current page. Total fetched: {len(all_job_postings)}")
            else:
                print("No jobs found on this page. Ending pagination.")
                break

            current_page_url = api_response.get("next")
            if not current_page_url:
                print("No 'next' page URL found. Ending pagination.")
                break

        except requests.exceptions.RequestException as e:
            frappe.log_error(f"Error fetching data from Ceipal API (Page: {current_page_url}): {e}", "CEIPAL API Error")
            print(f"Error fetching data from Ceipal API (Page: {current_page_url}):", str(e))
            return all_job_postings
        except Exception as e:
            frappe.log_error(f"General error during Ceipal job fetch (Page: {current_page_url}): {e}", "CEIPAL API Error")
            print(f"General error during Ceipal job fetch (Page: {current_page_url}):", str(e))
            return all_job_postings

    return all_job_postings


# ------------------ MAIN SYNC ------------------
@frappe.whitelist()
def custom_method():
    """Sync job postings from Ceipal → ERPNext Doctype"""
    frappe.msgprint("Starting Ceipal → ERPNext Job Sync")
    job_postings = get_ceipal_job_postings()

    print(f"Total Jobs Fetched from CEIPAL: {len(job_postings)}")
    frappe.logger().info(f"Total Jobs Fetched from CEIPAL: {len(job_postings)}")

    if not job_postings:
        return "No job postings found from Ceipal API."

    synced_count = 0
    errors_count = 0
    for job in job_postings:
        print("\nProcessing Job Data ========================")

        res = sync_erpnext_document(job)
        if res:
            synced_count += 1
        else:
            errors_count += 1
            frappe.log_error(f"Failed to sync job: {job.get('id', 'N/A')} - {job.get('position_title', 'N/A')}", "CEIPAL Job Sync Error")

    frappe.db.commit()
    return f"Ceipal Job Sync Complete! Successfully synced {synced_count} job postings. Failed: {errors_count}."


# ------------------ ERPNext Sync ------------------
def sync_erpnext_document(job_data):
    """Create/Update ERPNext Job Creation document from CEIPAL data"""
    headers = {
        "Authorization": f"token {ERPNEXT_API_KEY}:{ERPNEXT_API_SECRET}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }

    ceipal_unique_id = job_data.get("id")
    if not ceipal_unique_id:
        print("Skipping job, missing unique 'id' from CEIPAL:", job_data.get("position_title", "Unknown Job"))
        frappe.logger().info(f"Skipping job, missing unique 'id' from CEIPAL: {job_data.get('position_title', 'Unknown Job')}")
        return None

    existing_doc_name = None
    try:
        existing_docs = frappe.get_list(ERPNEXT_DOCTYPE,
                                        filters={"ceipal_ref": ceipal_unique_id},
                                        fields=["name"])
        if existing_docs:
            existing_doc_name = existing_docs[0].get("name")
            print(f"Found existing ERPNext document '{existing_doc_name}' for CEIPAL ID {ceipal_unique_id}")
            frappe.logger().info(f"Found existing ERPNext document '{existing_doc_name}' for CEIPAL ID {ceipal_unique_id}")
        else:
            print(f"No existing ERPNext document found for CEIPAL ID {ceipal_unique_id}")

    except Exception as e:
        frappe.log_error(f"Error checking for existing document in ERPNext for CEIPAL ID {ceipal_unique_id}: {e}", "CEIPAL Sync Error")
        print("Error checking for existing document in ERPNext:", str(e))
        return None

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
        if isinstance(value, str) and value.strip() == "":
            data_to_sync[key] = None

    print(f"Data prepared for ERPNext Sync for job '{job_data.get('position_title')}':")
    frappe.logger().info(f"Data prepared for ERPNext Sync for job '{job_data.get('position_title')}': {json.dumps(data_to_sync, indent=2)}")

    try:
        if existing_doc_name:
            print(f"Updating existing ERPNext Job Creation: {existing_doc_name} (CEIPAL ID: {ceipal_unique_id})")
            doc = frappe.get_doc(ERPNEXT_DOCTYPE, existing_doc_name)
            doc.update(data_to_sync)
            doc.save(ignore_permissions=True)
            doc.submit()  # ✅ Ensure submitted

            print(f"Updated & Submitted ERPNext document: {doc.name}")
            return {"status": "updated", "doc_name": doc.name}
        else:
            print(f"Creating new ERPNext Job Creation document for CEIPAL ID: {ceipal_unique_id}")
            doc = frappe.new_doc(ERPNEXT_DOCTYPE)
            doc.update(data_to_sync)
            doc.insert(ignore_permissions=True)
            doc.submit()  # ✅ Ensure submitted

            print(f"Created & Submitted new ERPNext document: {doc.name}")
            return {"status": "created", "doc_name": doc.name}

    except Exception as e:
        frappe.log_error(f"Error creating/updating ERPNext Job Creation for CEIPAL ID {ceipal_unique_id}: {e}", "CEIPAL Sync Error")
        print(f"Error creating/updating ERPNext Job Creation for CEIPAL ID {ceipal_unique_id}: {str(e)}")
        return None
