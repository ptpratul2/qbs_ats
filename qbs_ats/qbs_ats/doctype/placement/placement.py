import frappe
from frappe.model.document import Document
import requests
import os
import urllib.parse
import re
from requests.adapters import HTTPAdapter
from requests.packages.urllib3.util.retry import Retry

from qbs_ats.qbs_ats.doctype.job_creation.job_creation import (
    get_active_token,
    generate_ceipal_token,
)

CEIPAL_PLACEMENTS_API = "https://api.ceipal.com/v1/getPlacementsList?"


class Placement(Document):
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


@frappe.whitelist()
def custom_method(batch_size=50, start_page=1, max_pages=None):
    """Fetch placements from CEIPAL API and sync into ERPNext."""
    frappe.logger().info(" Starting CEIPAL Placements Sync...")

    token = get_active_token()
    if not token:
        token_data = generate_ceipal_token()
        if not token_data or not token_data.get("access_token"):
            frappe.log_error(" Failed to generate CEIPAL token. Sync stopped.", "CEIPAL Placements Sync")
            return
        token = token_data.get("access_token")

    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    session = requests_session()

    created_count, updated_count, skipped_count = 0, 0, 0
    page, has_more = start_page, True

    while has_more:
        if max_pages and page > max_pages:
            break

        next_page_url = f"{CEIPAL_PLACEMENTS_API}page={page}&limit={batch_size}"
        frappe.logger().info(f" Fetching placements from: {next_page_url}")

        try:
            response = session.get(next_page_url, headers=headers, timeout=300)

            if response.status_code in [401, 403]:
                token_data = generate_ceipal_token()
                if not token_data or not token_data.get("access_token"):
                    frappe.log_error(f"Token error ({response.status_code}). Regeneration failed.", "CEIPAL Placements Sync")
                    return
                token = token_data.get("access_token")
                headers["Authorization"] = f"Bearer {token}"
                response = session.get(next_page_url, headers=headers, timeout=300)

            response.raise_for_status()
            data = response.json()

        except Exception as e:
            frappe.log_error(f" Request failed for {next_page_url}: {str(e)}", "CEIPAL Placements Sync")
            break

        placements_from_api = data.get("results", [])
        if not placements_from_api:
            has_more = False
            break

        for record in placements_from_api:
            try:
                placement_id = record.get("placement_id")

                existing_doc_name = None
                if placement_id:
                    existing_doc_name = frappe.db.get_value(
                        "Placement",
                        {"placement_id": placement_id, "docstatus": ("!=", 2)},
                        "name",
                    )

                erpnext_placement_data = {
                    "placement_id": placement_id,
                    "client_name": record.get("client_name"),
                    "job_start_date": record.get("job_start_date"),
                    "job_end_date": record.get("job_end_date"),
                    "revenue_type": record.get("revenue_type"),
                    "employee_name": record.get("employee_name"),
                    "employee_number": record.get("employee_number"),
                    "email": record.get("email"),
                    "placement_status": record.get("placement_status"),
                    "created": record.get("created"),
                    "modified1": record.get("modified"),
                    "is_confirmation": record.get("is_confirmation"),
                    "business_unit_id": record.get("business_unit_id"),
                    "created_by": record.get("created_by"),
                    "modified_by": record.get("modified_by"),
                }

                placement_doc = None
                if existing_doc_name:
                    placement_doc = frappe.get_doc("Placement", existing_doc_name)
                    if placement_doc.docstatus == 1:  # already submitted → skip
                        skipped_count += 1
                        continue
                    placement_doc.update(erpnext_placement_data)
                    placement_doc.save(ignore_permissions=True)
                    updated_count += 1
                else:
                    placement_doc = frappe.new_doc("Placement")
                    placement_doc.update(erpnext_placement_data)
                    placement_doc.insert(ignore_permissions=True)
                    created_count += 1

                if placement_doc and placement_doc.docstatus == 0:
                    placement_doc.submit()

            except Exception as e:
                frappe.log_error(
                    f" Failed to process placement {record.get('placement_id')}: {str(e)}",
                    "CEIPAL Placements Sync",
                )

        frappe.db.commit()
        page += 1 if data.get("next") else 0
        has_more = bool(data.get("next"))

    frappe.logger().info(
        f" Sync completed. Created: {created_count}, Updated: {updated_count}, Skipped: {skipped_count}."
    )


@frappe.whitelist()
def enqueue_get_placements(batch_size=50, start_page=1, max_pages=None):
    """Trigger placements sync from CEIPAL to ERPNext in background queue."""
    frappe.enqueue(
        "qbs_ats.qbs_ats.doctype.placement.placement.custom_method",
        batch_size=batch_size,
        start_page=start_page,
        max_pages=max_pages,
        queue="long"
    )
    return {"status": "queued", "message": "Placements GET job enqueued"}