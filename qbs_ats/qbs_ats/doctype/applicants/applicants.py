import frappe
from frappe.model.document import Document
import requests
import re
import time
import os
import mimetypes
import urllib.parse
from requests.adapters import HTTPAdapter
from requests.packages.urllib3.util.retry import Retry

from qbs_ats.qbs_ats.doctype.job_creation.job_creation import (
    get_active_token,
    generate_ceipal_token,
)

CEIPAL_APPLICANTS_API = "https://api.ceipal.com/v1/getApplicantsList?"
CEIPAL_USERS_API = "https://api.ceipal.com/v1/getUsersList?"


class Applicants(Document):
    pass


def requests_session():
    """Create a requests session with retry & backoff strategy."""
    session = requests.Session()
    retries = Retry(
        total=5,
        backoff_factor=3,
        status_forcelist=[403, 429, 500, 502, 503, 504],
        allowed_methods=["GET", "POST"],
    )
    adapter = HTTPAdapter(max_retries=retries)
    session.mount("http://", adapter)
    session.mount("https://", adapter)
    return session


def get_ceipal_users_map(token):
    """Fetch all Ceipal users and return mapping {user_id: display_name}."""
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
                name = (
                    user.get("display_name")
                    or user.get("name")
                    or user.get("username")
                )
                if uid and name:
                    users_map[uid] = name

            next_page_url = data.get("next")

        return users_map

    except Exception as e:
        frappe.log_error(f"Failed to fetch Ceipal users list: {str(e)}", "CEIPAL Users Sync")
        return {}


# -------------------- DOWNLOAD RESUME --------------------
def download_and_attach_resume(doc, resume_url, applicant_name, token):
    """Downloads the resume and attaches it to the Applicant document."""
    if not resume_url:
        return

    session = requests_session()
    headers = {"Authorization": f"Bearer {token}"}

    try:
        safe_url = urllib.parse.quote(resume_url, safe=":/?&=%")

        print(f"Downloading resume for {applicant_name} from: {safe_url}")
        response = session.get(safe_url, headers=headers, stream=True, timeout=120)

        if response.status_code == 400:
            frappe.log_error(
                message=f"Resume download failed (400) for {applicant_name}. URL may be expired.\nURL: {resume_url}",
                title="CEIPAL Resume Sync",
            )
            return

        response.raise_for_status()

        filename = None
        if "Content-Disposition" in response.headers:
            match = re.findall(
                r"filename\*?=['\"]?(?:utf-\d['\"]*)?([^;'\"]+)",
                response.headers["Content-Disposition"],
            )
            if match:
                filename = requests.utils.unquote(match[0])

        if not filename:
            path = resume_url.split("?")[0]
            filename = os.path.basename(path) or f"{applicant_name}_resume.pdf"

        filename = re.sub(r"[^\w_.-]", "_", filename)

        file_content = b""
        for chunk in response.iter_content(chunk_size=8192):
            file_content += chunk

        if not file_content:
            frappe.log_error(
                message=f"Empty resume content for {applicant_name}. URL: {resume_url}",
                title="CEIPAL Resume Sync",
            )
            return

        file_doc = frappe.new_doc("File")
        file_doc.file_name = filename
        file_doc.attached_to_doctype = doc.doctype
        file_doc.attached_to_name = doc.name
        file_doc.content = file_content
        file_doc.is_private = 1
        file_doc.insert(ignore_permissions=True)
        frappe.db.commit()

        doc.db_set("resume", file_doc.file_url)
        print(f" Resume {filename} attached to Applicant {doc.name}")

    except requests.exceptions.RequestException as e:
        frappe.log_error(
            message=f"Request error downloading resume for {applicant_name} from {resume_url}\nError: {str(e)}",
            title="CEIPAL Resume Sync",
        )
    except Exception as e:
        frappe.log_error(
            message=f"General error attaching resume for {applicant_name}.\nURL: {resume_url}\nError: {str(e)}",
            title="CEIPAL Resume Sync",
        )


@frappe.whitelist()
def custom_method(batch_size=50, start_page=1, max_pages=None):
    """Fetch all applicants from CEIPAL API with retry + timeout + pagination + batch processing."""
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

        created_count, updated_count, skipped_count = 0, 0, 0
        page, has_more = start_page, True

        while has_more:
            if max_pages and page > max_pages:
                print(f"Reached max_pages limit: {max_pages}")
                break

            next_page_url = f"{CEIPAL_APPLICANTS_API}page={page}"
            print(f"Fetching applicants from: {next_page_url}")

            try:
                response = session.get(next_page_url, headers=headers, timeout=90)

                if response.status_code in [401, 403]:
                    frappe.logger().info(
                        f"CEIPAL token expired/forbidden ({response.status_code}). Regenerating..."
                    )
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
                frappe.logger().info(f"Timeout fetching: {next_page_url}, retrying after 5s...")
                time.sleep(5)
                continue
            except Exception as e:
                frappe.log_error(f"Request failed for {next_page_url}: {str(e)}", "CEIPAL Applicants Sync")
                break

            applicants_from_api = data.get("results", [])
            print(f"Page {page}: received {len(applicants_from_api)} applicants")

            if not applicants_from_api:
                has_more = False
                break

            # Process in batches
            for i in range(0, len(applicants_from_api), batch_size):
                batch = applicants_from_api[i:i + batch_size]
                print(f"Processing batch {i//batch_size + 1} (size {len(batch)}) from page {page}")

                for applicant_data in batch:
                    try:
                        email = applicant_data.get("email")
                        applicant_id = applicant_data.get("applicant_id")
                        applicant_full_name = f"{applicant_data.get('firstname', '')} {applicant_data.get('lastname', '')}".strip()

                        # Check if applicant exists
                        existing_doc_name = None
                        if email:
                            existing_doc_name = frappe.db.get_value(
                                "Applicants",
                                {"email_address": email, "docstatus": ("!=", 2)},
                                "name",
                            )
                        if not existing_doc_name and applicant_id:
                            existing_doc_name = frappe.db.get_value(
                                "Applicants",
                                {"applicant_id": applicant_id, "docstatus": ("!=", 2)},
                                "name",
                            )

                        raw_created_by = applicant_data.get("created_by")
                        created_by_name = users_map.get(raw_created_by, raw_created_by)

                        erpnext_applicant_data = {
                            "applicant_id": applicant_id,
                            "data_css": applicant_data.get("firstname"),
                            "last_name": applicant_data.get("lastname"),
                            "email_address": email,
                            "mobile_number": re.sub(r"\D", "", str(applicant_data.get("mobile_number", ""))),
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

                        applicant_doc = None
                        if existing_doc_name:
                            applicant_doc = frappe.get_doc("Applicants", existing_doc_name)
                            if applicant_doc.docstatus == 1:
                                skipped_count += 1
                                print(f"Applicant {applicant_doc.name} already submitted, skipping.")
                                continue
                            applicant_doc.update(erpnext_applicant_data)
                            applicant_doc.save(ignore_permissions=True)
                            updated_count += 1
                            print(f"Applicant updated: {applicant_doc.name}")
                        else:
                            applicant_doc = frappe.new_doc("Applicants")
                            applicant_doc.update(erpnext_applicant_data)
                            applicant_doc.insert(ignore_permissions=True)
                            created_count += 1
                            print(f"Applicant created: {applicant_doc.name}")

                        if applicant_doc:
                            resume_path = applicant_data.get("resume_path")
                            if resume_path:
                                download_and_attach_resume(applicant_doc, resume_path, applicant_full_name, token)

                            if applicant_doc.docstatus == 0:
                                applicant_doc.submit()

                    except Exception as e:
                        frappe.log_error(f"Failed to process applicant {applicant_data.get('applicant_id')}: {str(e)}", "CEIPAL Applicant Sync")

                frappe.db.commit()
                time.sleep(1)

            if data.get("next"):
                page += 1
            else:
                has_more = False

        success_message = f"Sync completed. Created: {created_count}, Updated: {updated_count}, Skipped: {skipped_count}."
        print(success_message)
        return {"status": "success", "message": success_message, "created": created_count, "updated": updated_count, "skipped": skipped_count}

    except Exception as e:
        frappe.log_error(f"Applicants Sync error: {str(e)}", "CEIPAL Applicants Sync")
        return {"status": "error", "message": f"Unexpected error: {str(e)}"}
