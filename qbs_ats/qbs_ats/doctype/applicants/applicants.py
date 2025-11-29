




import frappe
from frappe.model.document import Document
import requests
import re
import os
import urllib.parse
import time
import random  # Random delay ke liye
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
    """Logs error safely ensuring title is within limit."""
    try:
        clean_title = str(title).strip()
        short_title = clean_title[:139] if clean_title else "CEIPAL Unknown Error"
        frappe.log_error(message, short_title)
    except Exception:
        print(f"CRITICAL: Logging Failed: {title}")

def log_debug(message):
    try:
        frappe.logger("ceipal_sync").info(f"[CEIPAL DEBUG] {message}")
    except Exception:
        pass

def requests_session():
    """Creates a session with Browser-like headers to avoid blocking."""
    try:
        session = requests.Session()
        retries = Retry(
            total=3,
            backoff_factor=2, 
            status_forcelist=[500, 502, 503, 504], # 403 ko yahan handle nahi karenge, loop mein karenge
            allowed_methods=["GET", "POST"],
        )
        adapter = HTTPAdapter(max_retries=retries)
        session.mount("http://", adapter)
        session.mount("https://", adapter)
        
        # Ye header server ko batata hai ki hum browser hain, bot nahi
        session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
            "Accept": "application/json"
        })
        return session
    except Exception as e:
        safe_log_error(f"Session Creation Failed: {str(e)}", "CEIPAL Session Error")
        raise e

# --- CORE LOGIC ---

def get_ceipal_users_map(token):
    # (Ye function same rahega, isme issue nahi hai)
    cache_key = "ceipal_users_map_cache"
    try:
        cached_users = frappe.cache().get_value(cache_key)
        if cached_users: return cached_users
    except Exception: pass

    users_map = {}
    next_page_url = CEIPAL_USERS_API
    session = requests_session()
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

    try:
        while next_page_url:
            try:
                response = session.get(next_page_url, headers=headers, timeout=60)
                if response.status_code != 200: break
                data = response.json()
            except Exception: break

            results = data.get("results") or data.get("data") or []
            for user in results:
                uid = user.get("id")
                name = user.get("display_name") or user.get("name")
                if uid and name: users_map[uid] = name

            next_page_url = data.get("next")
            time.sleep(0.5) 

        if users_map:
            frappe.cache().set_value(cache_key, users_map, expires_in_sec=3600)
        return users_map
    except Exception:
        return {}

def download_and_attach_resume(doc_name, resume_url, applicant_name, token):
    # Resume download logic with better error handling
    if not resume_url: return
    session = requests_session()
    headers = {"Authorization": f"Bearer {token}"}

    try:
        safe_url = urllib.parse.quote(resume_url, safe=":/?&=%")
        try:
            response = session.get(safe_url, headers=headers, stream=True, timeout=120)
            if response.status_code == 401:
                 # Token refresh logic here if needed
                 pass
            if response.status_code in [403, 404]: return 
            response.raise_for_status()
        except Exception: return

        # Filename logic
        filename = "resume.pdf"
        try:
            if "Content-Disposition" in response.headers:
                match = re.findall(r"filename\*?=['\"]?(?:utf-\d['\"]*)?([^;'\"]+)", response.headers["Content-Disposition"])
                if match: filename = requests.utils.unquote(match[0])
            else:
                filename = os.path.basename(resume_url.split("?")[0]) or f"{applicant_name}.pdf"
            filename = re.sub(r"[^\w_.-]", "_", filename)
        except Exception: pass

        # Attach
        try:
            if not frappe.db.exists("Applicants", doc_name): return
            doc = frappe.get_doc("Applicants", doc_name)
            
            file_doc = frappe.new_doc("File")
            file_doc.file_name = filename
            file_doc.attached_to_doctype = doc.doctype
            file_doc.attached_to_name = doc.name
            file_doc.content = response.content
            file_doc.is_private = 1
            file_doc.insert(ignore_permissions=True)
            frappe.db.commit()
            doc.db_set("resume", file_doc.file_url)
        except Exception: pass
    except Exception: pass


@frappe.whitelist()
def custom_method(batch_size=50, start_page=1752, max_pages=3000):
    log_debug(f"Starting Sync from Page {start_page}...")

    # --- TOKEN SETUP ---
    try:
        token = get_active_token()
        if not token:
            token_data = generate_ceipal_token()
            token = token_data.get("access_token")
    except Exception as e:
        safe_log_error(f"Token Error: {str(e)}", "CEIPAL Token Error")
        return

    session = requests_session()
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    users_map = get_ceipal_users_map(token)

    created_count = updated_count = skipped_count = 0
    page = int(start_page)
    max_pages = int(max_pages) if max_pages else 10000
    has_more = True
    session_request_count = 0

    # --- MAIN LOOP ---
    try:
        while has_more:
            if page > max_pages: break

            # 1. Session Refresh (Prevent Stale Connection)
            if session_request_count > 50:
                session.close()
                session = requests_session()
                session_request_count = 0
                log_debug("Refreshing Session...")

            # 2. Random Sleep (Prevent 403 Blocking)
            # Har request ke baad 1.5 se 3 second rukenge
            time.sleep(random.uniform(1.5, 3.0))

            next_page_url = f"{CEIPAL_APPLICANTS_API}page={page}&limit={batch_size}"
            
            try:
                response = session.get(next_page_url, headers=headers, timeout=120)
                session_request_count += 1

                # 3. Handle Blocking (403/429)
                if response.status_code in [403, 429]:
                    safe_log_error(f"Rate Limited (403) at Page {page}. Waiting 60s...", "CEIPAL Cooldown")
                    time.sleep(60) # 1 Minute wait
                    
                    # Naya session aur token try karein
                    session = requests_session()
                    token_data = generate_ceipal_token()
                    if token_data:
                        token = token_data.get("access_token")
                        headers["Authorization"] = f"Bearer {token}"
                    
                    # Ek baar retry karein
                    response = session.get(next_page_url, headers=headers, timeout=120)
                    if response.status_code in [403, 429]:
                        safe_log_error("Still blocked. Stopping script safely.", "CEIPAL Stop")
                        break

                if response.status_code == 401:
                    # Token expired logic
                    token_data = generate_ceipal_token()
                    if token_data:
                        token = token_data.get("access_token")
                        headers["Authorization"] = f"Bearer {token}"
                        response = session.get(next_page_url, headers=headers, timeout=120)

                response.raise_for_status()
                data = response.json()

            except Exception as api_err:
                safe_log_error(f"API Failed at Page {page}: {str(api_err)}", "CEIPAL API Error")
                # Agar API fail hui, to aage badhne ka fayda nahi, break karein
                break

            applicants_from_api = data.get("results", [])
            
            if not applicants_from_api:
                log_debug("No more data found.")
                has_more = False
                break

            # --- DATA SAVING LOGIC ---
            for applicant_data in applicants_from_api:
                try:
                    email = applicant_data.get("email")
                    applicant_id = applicant_data.get("applicant_id")
                    
                    if not email and not applicant_id: continue

                    # Duplicate Check
                    existing_name = None
                    if email:
                        existing_name = frappe.db.get_value("Applicants", {"email_address": email}, "name")
                    if not existing_name and applicant_id:
                        existing_name = frappe.db.get_value("Applicants", {"applicant_id": applicant_id}, "name")

                    # Submitted Doc Check
                    if existing_name:
                        if frappe.db.get_value("Applicants", existing_name, "docstatus") == 1:
                            skipped_count += 1
                            continue

                    # Mapping
                    raw_created = applicant_data.get("created_by")
                    created_by_name = users_map.get(raw_created, raw_created)
                    
                    row_data = {
                        "applicant_id": applicant_id,
                        "data_css": applicant_data.get("firstname"),
                        "last_name": applicant_data.get("lastname"),
                        "email_address": email,
                        "mobile_number": re.sub(r"\D", "", str(applicant_data.get("mobile_number", ""))),
                        "skills": applicant_data.get("skills"),
                        "job_title": applicant_data.get("job_title"),
                        "created_by": created_by_name,
                        "created_on": applicant_data.get("created_at"),
                        # ... baaki fields same rahein ...
                        "source": applicant_data.get("source"),
                        "city": applicant_data.get("city"),
                        "state": applicant_data.get("state"),
                        "country": applicant_data.get("country"),
                    }

                    if existing_name:
                        frappe.db.set_value("Applicants", existing_name, row_data)
                        applicant_doc_name = existing_name
                        updated_count += 1
                    else:
                        doc = frappe.new_doc("Applicants")
                        doc.update(row_data)
                        doc.insert(ignore_permissions=True)
                        applicant_doc_name = doc.name
                        created_count += 1

                    # Resume Background Job
                    resume_path = applicant_data.get("resume_path")
                    if resume_path:
                        frappe.enqueue(
                            "qbs_ats.qbs_ats.doctype.applicants.applicants.download_and_attach_resume",
                            doc_name=applicant_doc_name,
                            resume_url=resume_path,
                            applicant_name=f"{row_data['data_css']} {row_data['last_name']}",
                            token=token,
                            queue="long"
                        )
                    
                    # Auto Submit
                    try:
                        current_doc = frappe.get_doc("Applicants", applicant_doc_name)
                        if current_doc.docstatus == 0: current_doc.submit()
                    except Exception: pass

                except Exception as row_err:
                    log_debug(f"Row Error: {str(row_err)}")
                    continue

            frappe.db.commit() # Batch Commit
            
            if not data.get("next"): has_more = False
            
            page += 1
            if page % 10 == 0:
                log_debug(f"Progress: Page {page} done. Created: {created_count}")

    except Exception as e:
        safe_log_error(f"Critical Error: {str(e)}", "CEIPAL Main Error")


@frappe.whitelist()
def enqueue_get_applicants(batch_size=50, start_page=1, max_pages=None):
    frappe.enqueue(
        "qbs_ats.qbs_ats.doctype.applicants.applicants.custom_method",
        batch_size=batch_size,
        start_page=start_page,
        max_pages=max_pages,
        queue="long",
        timeout=10000
    )
    return {"status": "queued", "message": f"Job started from page {start_page}"}