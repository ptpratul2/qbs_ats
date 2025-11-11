import frappe
from frappe.model.document import Document
import requests
import re
import os
import urllib.parse
from requests.adapters import HTTPAdapter
from requests.packages.urllib3.util.retry import Retry

from qbs_ats.qbs_ats.doctype.job_creation.job_creation import (
    get_active_token,
    generate_ceipal_token,
)

CEIPAL_APPLICANTS_API = "https://api.ceipal.com/v1/getApplicantsList?"
CEIPAL_USERS_API = "https://api.ceipal.com/v1/getUsersList?"
CEIPAL_CREATE_APPLICANT_API = "https://api.ceipal.com/v1/createApplicant"


class Applicants(Document):
    pass


def log_debug(message):
    """Helper for improved debug logging."""
    frappe.logger().info(f"[CEIPAL DEBUG] {message}")


def requests_session():
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
    log_debug("Requests session created with retry strategy.")
    return session


def get_ceipal_users_map(token):
    log_debug("Fetching CEIPAL Users list...")
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    users_map = {}
    next_page_url = CEIPAL_USERS_API
    session = requests_session()

    try:
        while next_page_url:
            log_debug(f"Fetching CEIPAL Users URL: {next_page_url}")
            response = session.get(next_page_url, headers=headers, timeout=120)
            response.raise_for_status()

            data = response.json()
            results = data.get("results") or data.get("data") or []

            log_debug(f"Users fetched count: {len(results)}")

            for user in results:
                uid = user.get("id")
                name = (
                    user.get("display_name")
                    or user.get("name")
                    or user.get("username")
                )
                if uid and name:
                    users_map[uid] = name
                else:
                    log_debug(f"User entry missing id or name: {user}")

            next_page_url = data.get("next")

        log_debug(f"Total CEIPAL users mapped: {len(users_map)}")
        return users_map

    except Exception as e:
        frappe.log_error(
            f"[ERROR] CEIPAL Users Sync failed: {str(e)}",
            "CEIPAL Users Sync",
        )
        return {}


def download_and_attach_resume(doc_name, resume_url, applicant_name, token):
    log_debug(f"Starting resume download for {applicant_name}")
    if not resume_url:
        log_debug("No resume URL provided. Skipping.")
        return

    session = requests_session()
    headers = {"Authorization": f"Bearer {token}"}

    try:
        safe_url = urllib.parse.quote(resume_url, safe=":/?&=%")
        log_debug(f"Downloading resume from URL: {safe_url}")

        response = session.get(safe_url, headers=headers, stream=True, timeout=300)

        if response.status_code == 400:
            frappe.log_error(
                f"[ERROR 400] Resume download failed for {applicant_name}. URL expired? {resume_url}",
                "CEIPAL Resume Sync",
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
                f"[ERROR] Empty resume content for {applicant_name}. URL: {resume_url}",
                "CEIPAL Resume Sync",
            )
            return

        doc = frappe.get_doc("Applicants", doc_name)

        file_doc = frappe.new_doc("File")
        file_doc.file_name = filename
        file_doc.attached_to_doctype = doc.doctype
        file_doc.attached_to_name = doc.name
        file_doc.content = file_content
        file_doc.is_private = 1
        file_doc.insert(ignore_permissions=True)
        frappe.db.commit()

        doc.db_set("resume", file_doc.file_url)
        log_debug(f"Resume attached successfully: {filename}")

    except Exception as e:
        frappe.log_error(
            f"[ERROR] Resume download error for {applicant_name}: {str(e)}",
            "CEIPAL Resume Sync",
        )


@frappe.whitelist()
def custom_method(batch_size=50, start_page=1, max_pages=None):
    log_debug("Starting CEIPAL Applicants Sync...")

    token = get_active_token()
    if not token:
        log_debug("Active token not found. Generating new one...")
        token_data = generate_ceipal_token()
        if not token_data or not token_data.get("access_token"):
            frappe.log_error("Token generation failed.", "CEIPAL Applicants Sync")
            return
        token = token_data.get("access_token")

    session = requests_session()
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    users_map = get_ceipal_users_map(token)

    created_count = updated_count = skipped_count = 0
    page = start_page
    has_more = True

    while has_more:
        if max_pages and page > max_pages:
            log_debug("Max page limit reached.")
            break

        next_page_url = f"{CEIPAL_APPLICANTS_API}page={page}&limit={batch_size}"
        log_debug(f"Fetching applicants from URL: {next_page_url}")

        try:
            response = session.get(next_page_url, headers=headers, timeout=300)

            if response.status_code in [401, 403]:
                log_debug(f"Token expired. Regenerating...")
                token_data = generate_ceipal_token()
                if not token_data or not token_data.get("access_token"):
                    frappe.log_error("Token regen failed.", "CEIPAL Applicants Sync")
                    return
                token = token_data["access_token"]
                headers["Authorization"] = f"Bearer {token}"
                response = session.get(next_page_url, headers=headers, timeout=300)

            response.raise_for_status()
            data = response.json()

        except Exception as e:
            frappe.log_error(f"[ERROR] Request failed: {str(e)}", "CEIPAL Applicants Sync")
            break

        applicants_from_api = data.get("results", [])
        log_debug(f"Applicants fetched: {len(applicants_from_api)}")

        if not applicants_from_api:
            log_debug("No more applicants found.")
            has_more = False
            break

        for applicant_data in applicants_from_api:
            try:
                email = applicant_data.get("email")
                applicant_id = applicant_data.get("applicant_id")
                applicant_full_name = f"{applicant_data.get('firstname', '')} {applicant_data.get('lastname', '')}".strip()

                log_debug(f"Processing applicant: {applicant_full_name} ({email})")

                existing_doc_name = None

                if email:
                    submitted_doc = frappe.db.get_value(
                        "Applicants",
                        {"email_address": email, "docstatus": 1},
                        "name",
                    )
                    if submitted_doc:
                        skipped_count += 1
                        log_debug("Skipping. Already submitted.")
                        continue

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
                    "consultant_name": applicant_data.get("consultant_name"),
                    "work_authorization_id": applicant_data.get("work_authorization_id"),
                    "home_phone_number": applicant_data.get("home_phone_number"),
                }

                if existing_doc_name:
                    applicant_doc = frappe.get_doc("Applicants", existing_doc_name)
                    if applicant_doc.docstatus == 1:
                        skipped_count += 1
                        log_debug("Skipping. Draft already submitted.")
                        continue
                    applicant_doc.update(erpnext_applicant_data)
                    applicant_doc.save(ignore_permissions=True)
                    updated_count += 1
                    log_debug(f"Applicant updated: {existing_doc_name}")

                else:
                    applicant_doc = frappe.new_doc("Applicants")
                    applicant_doc.update(erpnext_applicant_data)
                    applicant_doc.insert(ignore_permissions=True)
                    created_count += 1
                    log_debug(f"Applicant created: {applicant_doc.name}")

                resume_path = applicant_data.get("resume_path")
                if resume_path:
                    log_debug(f"Queueing resume download for {applicant_doc.name}")
                    frappe.enqueue(
                        "qbs_ats.qbs_ats.doctype.applicants.applicants.download_and_attach_resume",
                        doc_name=applicant_doc.name,
                        resume_url=resume_path,
                        applicant_name=applicant_full_name,
                        token=token,
                        queue="long",
                    )

                if applicant_doc.docstatus == 0:
                    applicant_doc.submit()

            except Exception as e:
                frappe.log_error(
                    f"[ERROR] Applicant processing failed for ID {applicant_data.get('applicant_id')}: {str(e)}",
                    "CEIPAL Applicant Sync",
                )

        frappe.db.commit()
        page += 1 if data.get("next") else 0
        has_more = bool(data.get("next"))

    log_debug(f"Sync complete | Created: {created_count}, Updated: {updated_count}, Skipped: {skipped_count}")


def post_applicant_to_ceipal(applicant_doc, token):
    log_debug(f"Posting applicant {applicant_doc.name} to CEIPAL...")

    session = requests_session()
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

    payload = {
        "firstname": applicant_doc.data_css,
        "lastname": applicant_doc.last_name,
        "email": applicant_doc.email_address,
        "mobile_number": applicant_doc.mobile_number,
        "skills": applicant_doc.skills,
        "job_title": applicant_doc.job_title,
    }

    log_debug(f"Payload: {payload}")

    try:
        response = session.post(CEIPAL_CREATE_APPLICANT_API, headers=headers, json=payload, timeout=120)
        response.raise_for_status()

        log_debug(f"Applicant posted successfully: {applicant_doc.name}")
        return response.json()

    except Exception as e:
        frappe.log_error(
            f"[ERROR] Failed to POST applicant {applicant_doc.name}: {str(e)}",
            "CEIPAL Post Applicant",
        )
        return None


@frappe.whitelist()
def enqueue_get_applicants(batch_size=50, start_page=1, max_pages=None):
    log_debug("Enqueueing GET applicants job...")
    frappe.enqueue(
        "qbs_ats.qbs_ats.doctype.applicants.applicants.custom_method",
        batch_size=batch_size,
        start_page=start_page,
        max_pages=max_pages,
        queue="long"
    )
    return {"status": "queued", "message": "Applicants GET job enqueued"}


@frappe.whitelist()
def enqueue_post_applicant(applicant_name):
    log_debug(f"Enqueueing POST applicant job: {applicant_name}")
    token = get_active_token()
    frappe.enqueue(
        "qbs_ats.qbs_ats.doctype.applicants.applicants.post_applicant_to_ceipal",
        applicant_doc=frappe.get_doc("Applicants", applicant_name),
        token=token,
        queue="long"
    )
    return {"status": "queued", "message": f"Applicant {applicant_name} POST job enqueued"}
