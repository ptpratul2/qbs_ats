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
            response = requests.get(current_page_url, headers=headers, timeout=30)
            if response.status_code == 429:
                frappe.logger().info("Rate limit hit (429). Sleeping for 60s...")
                time.sleep(60)
                continue

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
