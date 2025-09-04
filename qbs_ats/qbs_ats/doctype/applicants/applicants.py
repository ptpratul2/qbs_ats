# Copyright (c) 2025, Prompt Personnel and contributors
# For license information, please see license.txt

from frappe.model.document import Document
import frappe
import requests
import re

from qbs_ats.qbs_ats.doctype.job_creation.job_creation import get_active_token, generate_ceipal_token

CEIPAL_APPLICANTS_API = "https://api.ceipal.com/v1/getApplicantsList?"
CEIPAL_USERS_API = "https://api.ceipal.com/v1/getUsersList?"


class Applicants(Document):
    pass


def get_ceipal_users_map(token):
    """
    Fetch all Ceipal users and return mapping {user_id: display_name}.
    This helps us replace raw IDs with readable user names.
    """
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

    users_map = {}
    next_page_url = CEIPAL_USERS_API  

    try:
        while next_page_url:
            response = requests.get(next_page_url, headers=headers, timeout=120)
            response.raise_for_status()
            data = response.json()

            results = data.get("results") or data.get("data") or []
            for user in results:
                uid = user.get("id")
                name = user.get("display_name") or user.get("name") or user.get("username")
                if uid and name:
                    users_map[uid] = name

            # Check if more pages exist
            next_page_url = data.get("next")

        return users_map

    except Exception as e:
        frappe.log_error(f"Failed to fetch Ceipal users list: {str(e)}", "CEIPAL Users Sync")
        return {}


@frappe.whitelist()
def custom_method():
    """
    Fetch all applicants from CEIPAL API (paginated) 
    and create Applicants documents in ERPNext.
    Duplicate check added: skip if same email or applicant_id exists.
    """
    print("Starting CEIPAL Applicants Sync...")

    # 1. Get authentication token
    token = get_active_token()
    if not token:
        print("No active CEIPAL token found. Generating new one...")
        token_data = generate_ceipal_token()
        if not token_data or not token_data.get("access_token"):
            message = "Failed to generate CEIPAL token. Sync stopped."
            frappe.log_error(message, "CEIPAL Applicants Sync")
            return {"status": "error", "message": message}
        token = token_data.get("access_token")

    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

    try:
        users_map = get_ceipal_users_map(token)

        created_count = 0
        skipped_count = 0
        next_page_url = CEIPAL_APPLICANTS_API  # Start with first page

        while next_page_url:
            print(f"Fetching applicants from URL: {next_page_url}")
            response = requests.get(next_page_url, headers=headers, timeout=120)

            if response.status_code == 401:
                print("Token expired. Regenerating and retrying...")
                token_data = generate_ceipal_token()
                if not token_data or not token_data.get("access_token"):
                    message = "Token expired and regeneration failed. Sync stopped."
                    frappe.log_error(message, "CEIPAL Applicants Sync")
                    return {"status": "error", "message": message}
                token = token_data.get("access_token")
                headers["Authorization"] = f"Bearer {token}"
                response = requests.get(next_page_url, headers=headers, timeout=120 )

            response.raise_for_status()
            data = response.json()

            applicants_from_api = data.get("results", [])
            print(f"Processing {len(applicants_from_api)} applicants...")

            for applicant_data in applicants_from_api:
                try:
                    email = applicant_data.get("email")
                    applicant_id = applicant_data.get("applicant_id")

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
                        "created_by": created_by_name,  # readable name instead of raw id
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
                    print(f"Applicant created and submitted: {new_applicant_doc.name}")

                except Exception as e:
                    frappe.log_error(f"Failed to create applicant. Error: {str(e)}", "CEIPAL Applicant Creation")
                    print(f"Error creating applicant: {str(e)}")

            next_page_url = data.get("next")

        frappe.db.commit()

        success_message = f"Sync completed. Created: {created_count}, Skipped (duplicates): {skipped_count}."
        print(success_message)
        return {"status": "success", "message": success_message, "created": created_count, "skipped": skipped_count}

    except requests.exceptions.RequestException as e:
        frappe.log_error(f"CEIPAL API request error: {str(e)}", "CEIPAL Applicants Sync")
        print(f"API request exception: {str(e)}")
        return {"status": "error", "message": f"API request error: {str(e)}"}
    except Exception as e:
        frappe.log_error(f"Applicants Sync general error: {str(e)}", "CEIPAL Applicants Sync")
        print(f"General exception in Applicants Sync: {str(e)}")
        return {"status": "error", "message": f"Unexpected error: {str(e)}"}
