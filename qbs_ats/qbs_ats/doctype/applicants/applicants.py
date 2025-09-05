import frappe
from frappe.model.document import Document
import requests
import re
import time
from requests.adapters import HTTPAdapter
from requests.packages.urllib3.util.retry import Retry

from qbs_ats.qbs_ats.doctype.job_creation.job_creation import get_active_token, generate_ceipal_token

CEIPAL_APPLICANTS_API = "https://api.ceipal.com/v1/getApplicantsList?"
CEIPAL_USERS_API = "https://api.ceipal.com/v1/getUsersList?"


class Applicants(Document):
    pass


def requests_session():
    """Create a requests session with retry & backoff strategy."""
    session = requests.Session()
    retries = Retry(
        total=5,
        backoff_factor=3,  # exponential backoff (3s, 6s, 12s...)
        status_forcelist=[403, 429, 500, 502, 503, 504],
        allowed_methods=["GET", "POST"]
    )
    adapter = HTTPAdapter(max_retries=retries)
    session.mount("http://", adapter)
    session.mount("https://", adapter)
    return session


def get_ceipal_users_map(token):
    """
    Fetch all Ceipal users and return mapping {user_id: display_name}.
    """
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    users_map = {}
    next_page_url = CEIPAL_USERS_API
    session = requests_session()

    try:
        while next_page_url:
            response = session.get(next_page_url, headers=headers, timeout=60)
            response.raise_for_status()
            data = response.json()

            results = data.get("results") or data.get("data") or []
            for user in results:
                uid = user.get("id")
                name = user.get("display_name") or user.get("name") or user.get("username")
                if uid and name:
                    users_map[uid] = name

            next_page_url = data.get("next")

        return users_map

    except Exception as e:
        frappe.log_error(f"Failed to fetch Ceipal users list: {str(e)}", "CEIPAL Users Sync")
        return {}


@frappe.whitelist()
def custom_method(batch_size=50):
    """
    Fetch all applicants from CEIPAL API with retry + timeout + pagination handling.
    Processes in batches to avoid timeout.
    """
    print("Starting CEIPAL Applicants Sync...")

    token = get_active_token()
    if not token:
        token_data = generate_ceipal_token()
        if not token_data or not token_data.get("access_token"):
            message = "Failed to generate CEIPAL token. Sync stopped."
            frappe.log_error(message, "CEIPAL Applicants Sync")
            return {"status": "error", "message": message}
        token = token_data.get("access_token")

    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    session = requests_session()

    try:
        users_map = get_ceipal_users_map(token)

        created_count = 0
        skipped_count = 0
        page = 1
        has_more = True

        while has_more:
            next_page_url = f"{CEIPAL_APPLICANTS_API}page={page}"
            print(f"Fetching applicants from: {next_page_url}")

            try:
                response = session.get(next_page_url, headers=headers, timeout=90)

                if response.status_code in [401, 403]:
                    token_data = generate_ceipal_token()
                    if not token_data or not token_data.get("access_token"):
                        message = f"Token error ({response.status_code}). Regeneration failed."
                        frappe.log_error(message, "CEIPAL Applicants Sync")
                        return {"status": "error", "message": message}
                    token = token_data.get("access_token")
                    headers["Authorization"] = f"Bearer {token}"
                    response = session.get(next_page_url, headers=headers, timeout=90)

                response.raise_for_status()
                data = response.json()

            except requests.exceptions.Timeout:
                frappe.logger().info(f"Timeout fetching: {next_page_url}, retrying...")
                continue
            except Exception as e:
                frappe.log_error(f"Request failed for {next_page_url}: {str(e)}", "CEIPAL Applicants Sync")
                break

            applicants_from_api = data.get("results", [])
            print(f"Processing {len(applicants_from_api)} applicants from page {page}...")

            if not applicants_from_api:
                has_more = False
                break

            # ---------------- BATCH PROCESSING ----------------
            for i in range(0, len(applicants_from_api), batch_size):
                batch = applicants_from_api[i:i + batch_size]
                print(f"Processing batch {i//batch_size + 1} (size {len(batch)}) from page {page}")

                for applicant_data in batch:
                    try:
                        email = applicant_data.get("email")
                        applicant_id = applicant_data.get("applicant_id")

                        # skip if duplicate
                        if email and frappe.db.exists("Applicants", {"email_address": email}):
                            skipped_count += 1
                            continue
                        if applicant_id and frappe.db.exists("Applicants", {"applicant_id": applicant_id}):
                            skipped_count += 1
                            continue

                        raw_created_by = applicant_data.get("created_by")
                        created_by_name = users_map.get(raw_created_by, raw_created_by)

                        erpnext_applicant_data = {
                            "doctype": "Applicants",
                            "applicant_id": applicant_id,
                            "data_css": applicant_data.get("firstname"),
                            "last_name": applicant_data.get("lastname"),
                            "email_address": email,
                            "mobile_number": re.sub(r'\D', '', str(applicant_data.get("mobile_number", ""))),
                            "work_authorization": applicant_data.get("work_authorization"),
                            "address": applicant_data.get("address"),
                            "created_by": created_by_name,
                            "created_on": applicant_data.get("created_at"),
                            "country": applicant_data.get("country"),
                            "state": applicant_data.get("state"),
                            "city": applicant_data.get("city"),
                            "source": applicant_data.get("source"),
                            "applicant_status": applicant_data.get("applicant_status"),
                            "job_title": applicant_data.get("job_title"),
                            "skills": applicant_data.get("skills"),
                        }

                        new_applicant_doc = frappe.new_doc("Applicants")
                        new_applicant_doc.update(erpnext_applicant_data)
                        new_applicant_doc.insert(ignore_permissions=True)
                        new_applicant_doc.submit()

                        created_count += 1
                        print(f"Applicant created: {new_applicant_doc.name}")

                    except Exception as e:
                        frappe.log_error(f"Failed to create applicant: {str(e)}", "CEIPAL Applicant Creation")

                frappe.db.commit()  
                time.sleep(1)       

            if data.get("next"):
                page += 1
            else:
                has_more = False

        success_message = f"Sync completed. Created: {created_count}, Skipped (duplicates): {skipped_count}."
        print(success_message)
        return {"status": "success", "message": success_message, "created": created_count, "skipped": skipped_count}

    except Exception as e:
        frappe.log_error(f"Applicants Sync error: {str(e)}", "CEIPAL Applicants Sync")
        return {"status": "error", "message": f"Unexpected error: {str(e)}"}
