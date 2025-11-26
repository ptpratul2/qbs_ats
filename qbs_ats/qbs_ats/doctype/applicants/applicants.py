

import frappe
from frappe.model.document import Document
import requests
import re
import os
import urllib.parse
import time
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

# --- HELPER FUNCTIONS ---

def safe_log_error(message, title="CEIPAL Error"):
    """
    Logs error safely ensuring title is within 140 chars to prevent truncation error.
    """
    try:
        # Title ko 140 chars se chhota rakhna zaroori hai
        short_title = title[:139] if title else "CEIPAL Unknown Error"
        frappe.log_error(message, short_title)
    except Exception:
        # Fallback agar log_error khud fail ho jaye (rare case)
        print(f"CRITICAL: Logging Failed: {title} - {message}")

def log_debug(message):
    """Helper for improved debug logging."""
    try:
        # Aap chahein to 'ceipal_sync' ki jagah None use kar sakte hain
        frappe.logger("ceipal_sync").info(f"[CEIPAL DEBUG] {message}")
    except Exception:
        pass

def requests_session():
    """Creates a session with retry logic, but avoids 403 loops."""
    try:
        session = requests.Session()
        retries = Retry(
            total=3,
            backoff_factor=2, 
            status_forcelist=[429, 500, 502, 503, 504], # NOTE: 403 hata diya hai taaki block na ho
            allowed_methods=["GET", "POST"],
        )
        adapter = HTTPAdapter(max_retries=retries)
        session.mount("http://", adapter)
        session.mount("https://", adapter)
        
        # Adding User-Agent is crucial for some APIs to avoid blocking
        session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) ERPNext-Sync/1.0"
        })
        return session
    except Exception as e:
        safe_log_error(f"Failed to create Request Session: {str(e)}", "CEIPAL Session Error")
        # Agar session hi nahi bana, to code aage nahi chal sakta
        raise e

# --- CORE LOGIC ---

def get_ceipal_users_map(token):
    """Fetches users from Ceipal to map IDs to Names."""
    cache_key = "ceipal_users_map_cache"
    
    # Try getting from Cache
    try:
        cached_users = frappe.cache().get_value(cache_key)
        if cached_users:
            return cached_users
    except Exception as e:
        log_debug(f"Cache retrieval failed (Non-critical): {str(e)}")

    log_debug("Fetching CEIPAL Users list...")
    users_map = {}
    next_page_url = CEIPAL_USERS_API
    session = requests_session()
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

    try:
        while next_page_url:
            try:
                # API Call with Timeout
                response = session.get(next_page_url, headers=headers, timeout=60)
                
                if response.status_code == 401:
                    safe_log_error("Token expired while fetching users. Returning partial map.", "CEIPAL User Token Expired")
                    return users_map

                response.raise_for_status()
                data = response.json()
            except Exception as req_err:
                safe_log_error(f"HTTP Request failed for Users URL {next_page_url}: {str(req_err)}", "CEIPAL User API Error")
                break

            results = data.get("results") or data.get("data") or []

            for user in results:
                try:
                    uid = user.get("id")
                    name = (
                        user.get("display_name")
                        or user.get("name")
                        or user.get("username")
                    )
                    if uid and name:
                        users_map[uid] = name
                except Exception:
                    continue # Skip bad user record

            next_page_url = data.get("next")
            # Rate limiting protection (Wait 0.5 sec)
            time.sleep(0.5)

        # Cache result if successful (1 Hour)
        if users_map:
            frappe.cache().set_value(cache_key, users_map, expires_in_sec=3600)
        
        return users_map

    except Exception as e:
        safe_log_error(f"Critical error in User Sync Logic: {str(e)}", "CEIPAL Users Sync Critical")
        return {}

def download_and_attach_resume(doc_name, resume_url, applicant_name, token):
    log_debug(f"Starting resume download for {applicant_name}")
    if not resume_url:
        return

    session = requests_session()
    headers = {"Authorization": f"Bearer {token}"}

    try:
        safe_url = urllib.parse.quote(resume_url, safe=":/?&=%")
        
        # Step 1: Download
        try:
            response = session.get(safe_url, headers=headers, stream=True, timeout=120)
            
            if response.status_code == 401:
                # One retry for token
                new_token_data = generate_ceipal_token()
                if new_token_data and new_token_data.get("access_token"):
                    token = new_token_data.get("access_token")
                    headers["Authorization"] = f"Bearer {token}"
                    response = session.get(safe_url, headers=headers, stream=True, timeout=120)

            if response.status_code == 403:
                safe_log_error(f"403 Forbidden for resume URL: {safe_url}", "CEIPAL Resume 403")
                return

            response.raise_for_status()
        except Exception as dl_err:
            safe_log_error(f"Download request failed for {applicant_name}: {str(dl_err)}", "CEIPAL Resume Net Error")
            return

        # Step 2: Determine Filename
        filename = None
        try:
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
        except Exception as fn_err:
            filename = "resume.pdf" # Fallback
            log_debug(f"Filename parsing failed, using default. Error: {str(fn_err)}")

        # Step 3: Read Content
        try:
            file_content = b""
            for chunk in response.iter_content(chunk_size=8192):
                file_content += chunk

            if not file_content:
                safe_log_error(f"Downloaded file is empty for {applicant_name}", "CEIPAL Empty Resume")
                return
        except Exception as read_err:
             safe_log_error(f"Failed to read file content: {str(read_err)}", "CEIPAL File Read Error")
             return

        # Step 4: Attach to Frappe Doc
        try:
            # Check if doc still exists
            if not frappe.db.exists("Applicants", doc_name):
                log_debug(f"Applicant {doc_name} deleted before resume could attach.")
                return

            doc = frappe.get_doc("Applicants", doc_name)

            file_doc = frappe.new_doc("File")
            file_doc.file_name = filename
            file_doc.attached_to_doctype = doc.doctype
            file_doc.attached_to_name = doc.name
            file_doc.content = file_content
            file_doc.is_private = 1
            file_doc.insert(ignore_permissions=True)
            
            # Explicit commit needed for background jobs
            frappe.db.commit()

            doc.db_set("resume", file_doc.file_url)
            log_debug(f"Resume attached: {filename}")

        except Exception as attach_err:
            safe_log_error(f"DB Attach failed for {doc_name}: {str(attach_err)}", "CEIPAL File Attach Error")

    except Exception as e:
        safe_log_error(f"Unexpected error in resume logic: {str(e)}", "CEIPAL Resume Gen Error")


@frappe.whitelist()
def custom_method(batch_size=50, start_page=1, max_pages=None):
    log_debug("Starting CEIPAL Applicants Sync...")

    # --- TOKEN GENERATION BLOCK ---
    try:
        token = get_active_token()
        if not token:
            token_data = generate_ceipal_token()
            if not token_data or not token_data.get("access_token"):
                safe_log_error("Failed to generate initial token", "CEIPAL Token Gen Failed")
                return
            token = token_data.get("access_token")
    except Exception as e:
        safe_log_error(f"Token logic crashed: {str(e)}", "CEIPAL Token Logic Error")
        return

    session = requests_session()
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    
    # --- USER MAPPING BLOCK ---
    users_map = get_ceipal_users_map(token)

    created_count = updated_count = skipped_count = 0
    page = int(start_page)
    max_pages = int(max_pages) if max_pages else 10000
    has_more = True

    # --- MAIN SYNC LOOP ---
    try:
        while has_more:
            if page > max_pages:
                log_debug("Max page limit reached.")
                break

            next_page_url = f"{CEIPAL_APPLICANTS_API}page={page}&limit={batch_size}"
            log_debug(f"Fetching applicants Page: {page}")

            data = {}
            try:
                # Rate Limiting: Sleep to avoid 403/429
                time.sleep(1.0)
                
                response = session.get(next_page_url, headers=headers, timeout=120)

                # Token Refresh Logic
                if response.status_code == 401:
                    log_debug(f"Token expired at page {page}. Regenerating...")
                    token_data = generate_ceipal_token()
                    if not token_data or not token_data.get("access_token"):
                        safe_log_error("Token regen failed mid-sync.", "CEIPAL Sync Token Error")
                        break
                    token = token_data["access_token"]
                    headers["Authorization"] = f"Bearer {token}"
                    response = session.get(next_page_url, headers=headers, timeout=120)

                # Stop on Forbidden
                if response.status_code == 403:
                    safe_log_error(f"403 Forbidden at page {page}. Stopping sync.", "CEIPAL Sync 403")
                    break

                response.raise_for_status()
                data = response.json()

            except Exception as api_err:
                safe_log_error(f"API Request failed at page {page}: {str(api_err)}", "CEIPAL API Req Error")
                # Agar API call hi fail ho gayi, to loop break karna behtar hai
                break

            applicants_from_api = data.get("results", [])
            
            if not applicants_from_api:
                log_debug("No more applicants found in results.")
                has_more = False
                break

            # --- INDIVIDUAL APPLICANT PROCESSING ---
            for applicant_data in applicants_from_api:
                try:
                    email = applicant_data.get("email")
                    applicant_id = applicant_data.get("applicant_id")
                    
                    fname = applicant_data.get("firstname", "") or ""
                    lname = applicant_data.get("lastname", "") or ""
                    applicant_full_name = f"{fname} {lname}".strip()

                    # -- Duplicate Checks --
                    existing_doc_name = None

                    if email:
                        submitted_doc = frappe.db.get_value(
                            "Applicants",
                            {"email_address": email, "docstatus": 1},
                            "name",
                        )
                        if submitted_doc:
                            skipped_count += 1
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
                    
                    # Sanitize Mobile
                    raw_mobile = str(applicant_data.get("mobile_number", ""))
                    clean_mobile = re.sub(r"\D", "", raw_mobile) if raw_mobile else ""

                    erpnext_applicant_data = {
                        "applicant_id": applicant_id,
                        "data_css": fname,
                        "last_name": lname,
                        "email_address": email,
                        "mobile_number": clean_mobile,
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
                            continue
                        applicant_doc.update(erpnext_applicant_data)
                        applicant_doc.save(ignore_permissions=True)
                        updated_count += 1

                    else:
                        applicant_doc = frappe.new_doc("Applicants")
                        applicant_doc.update(erpnext_applicant_data)
                        applicant_doc.insert(ignore_permissions=True)
                        created_count += 1

                    # -- Resume Enqueue --
                    resume_path = applicant_data.get("resume_path")
                    if resume_path:
                        try:
                            frappe.enqueue(
                                "qbs_ats.qbs_ats.doctype.applicants.applicants.download_and_attach_resume",
                                doc_name=applicant_doc.name,
                                resume_url=resume_path,
                                applicant_name=applicant_full_name,
                                token=token,
                                queue="long",
                            )
                        except Exception as enq_err:
                            log_debug(f"Queueing failed for resume: {str(enq_err)}")

                    # -- Submit if Draft --
                    if applicant_doc.docstatus == 0:
                        try:
                            applicant_doc.submit()
                        except Exception as submit_err:
                            log_debug(f"Submit failed for {applicant_doc.name}: {str(submit_err)}")

                except Exception as row_err:
                    # Critical: Ye block ensure karta hai ki ek record fail hone se loop na toote
                    safe_log_error(f"Processing failed for Applicant ID {applicant_data.get('applicant_id')}: {str(row_err)}", "Applicant Save Error")
                    continue

            # Save batch progress
            frappe.db.commit()
            
            # Next Page logic
            if not data.get("next"):
                has_more = False
            
            page += 1

        log_debug(f"Sync complete | Created: {created_count}, Updated: {updated_count}, Skipped: {skipped_count}")

    except Exception as main_err:
        safe_log_error(f"Critical System Failure in Custom Method: {str(main_err)}", "CEIPAL CRITICAL SYSTEM ERROR")


def post_applicant_to_ceipal(applicant_doc, token):
    log_debug(f"Posting applicant {applicant_doc.name} to CEIPAL...")
    try:
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

        try:
            response = session.post(CEIPAL_CREATE_APPLICANT_API, headers=headers, json=payload, timeout=60)
            
            if response.status_code == 401:
                 # Retry once
                 token_data = generate_ceipal_token()
                 if token_data:
                     headers["Authorization"] = f"Bearer {token_data.get('access_token')}"
                     response = session.post(CEIPAL_CREATE_APPLICANT_API, headers=headers, json=payload, timeout=60)

            response.raise_for_status()
            log_debug(f"Applicant posted successfully: {applicant_doc.name}")
            return response.json()

        except Exception as post_req_err:
             safe_log_error(f"POST Request failed: {str(post_req_err)}", "CEIPAL POST Req Error")
             return None

    except Exception as e:
        safe_log_error(f"Failed to POST {applicant_doc.name}: {str(e)}", "CEIPAL Post Error")
        return None


@frappe.whitelist()
def enqueue_get_applicants(batch_size=50, start_page=1, max_pages=None):
    try:
        log_debug("Enqueueing GET applicants job...")
        frappe.enqueue(
            "qbs_ats.qbs_ats.doctype.applicants.applicants.custom_method",
            batch_size=batch_size,
            start_page=start_page,
            max_pages=max_pages,
            queue="long",
            timeout=3600
        )
        return {"status": "queued", "message": "Applicants GET job enqueued"}
    except Exception as e:
        safe_log_error(f"Enqueue GET failed: {str(e)}", "Enqueue GET Error")

@frappe.whitelist()
def enqueue_post_applicant(applicant_name):
    try:
        token = get_active_token()
        frappe.enqueue(
            "qbs_ats.qbs_ats.doctype.applicants.applicants.post_applicant_to_ceipal",
            applicant_doc=frappe.get_doc("Applicants", applicant_name),
            token=token,
            queue="long"
        )
        return {"status": "queued", "message": f"Applicant {applicant_name} POST job enqueued"}
    except Exception as e:
        safe_log_error(f"Enqueue POST failed: {str(e)}", "Enqueue POST Error")