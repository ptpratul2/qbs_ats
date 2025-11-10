

# Copyright (c) 2025, Prompt Personnel and contributors
# For license information, please see license.txt

from frappe.model.document import Document
import frappe
import requests
from qbs_ats.qbs_ats.doctype.job_creation.job_creation import (
    get_active_token,
    generate_ceipal_token
)

class NewClient(Document):
    pass

CEIPAL_CLIENT_API = "https://api.ceipal.com/v1/getClientsList?"
CEIPAL_CLIENT_DETAIL_API = "https://api.ceipal.com/v1/getClientDetails"

@frappe.whitelist()
def custom_method():
    """
    Fetch all CEIPAL clients + their contacts with pagination and sync into ERPNext.
    Avoid duplicates: if client already exists, update instead of creating new.
    """
    frappe.logger("ceipal_client_sync").info("Starting CEIPAL Client Sync")

    token = get_active_token()
    if not token:
        token_data = generate_ceipal_token()
        if not token_data or not token_data.get("access_token"):
            return {"status": "error", "message": "Failed to generate CEIPAL token."}
        token = token_data.get("access_token")

    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

    created_count, updated_count, error_count = 0, 0, 0
    next_page_url = CEIPAL_CLIENT_API

    while next_page_url:
        try:
            response = requests.get(next_page_url, headers=headers, timeout=30)
            response.raise_for_status()
            api_data = response.json()
        except Exception as e:
            frappe.log_error(f"Client list fetch failed: {e}", "CEIPAL Client Sync Error")
            break

        client_records = api_data.get("results", [])
        if not client_records:
            break

        for record in client_records:
            ceipal_id = record.get("id")
            if not ceipal_id:
                continue

            try:
                existing_client_name = frappe.db.get_value("New Client", {"ceipal_client_id": ceipal_id}, "name")
                if existing_client_name:
                    doc = frappe.get_doc("New Client", existing_client_name)
                    updated_count += 1
                else:
                    doc = frappe.new_doc("New Client")
                    doc.ceipal_client_id = ceipal_id
                    created_count += 1

                doc.client_name = record.get("name") or ""
                doc.country = record.get("country") or ""
                doc.state = record.get("state") or ""
                doc.city = record.get("city") or ""
                doc.postal_code = record.get("zipcode") or ""
                doc.status = record.get("status") or ""
                doc.category = record.get("category") or ""
                doc.created_at = record.get("created_at") or ""
                doc.update_at = record.get("updated_at") or ""
                doc.industry = record.get("industry_exp") or ""
                doc.primary_business_unit = record.get("primary_business_unit") or ""
                doc.accessible_business_unites = record.get("accessible_business_units") or ""

                detail_url = f"{CEIPAL_CLIENT_DETAIL_API}?client_id={ceipal_id}"
                try:
                    detail_res = requests.get(detail_url, headers=headers, timeout=30)
                    detail_res.raise_for_status()
                    detail_data = detail_res.json()
                except Exception as e:
                    frappe.log_error(f"Details fetch failed for {ceipal_id}: {e}", "CEIPAL Client Detail Error")
                    continue

                doc.set("contact_details", [])
                contacts = detail_data.get("contacts", [])
                for c in contacts:
                    doc.append("contact_details", {
                        "first_name": c.get("contact_first_name") or "",
                        "last_name": c.get("contact_last_name") or "",
                        "email": c.get("email_id") or "",
                        "mobile_no": c.get("mobile_no") or "",
                        "contact_status": c.get("client_contact_status") or "",
                        "address_line1": c.get("address1") or "",
                        "address_line2": c.get("address2") or ""
                    })

                if doc.is_new():
                    doc.insert(ignore_permissions=True)
                else:
                    doc.save(ignore_permissions=True)

                if doc.docstatus == 0:
                    doc.submit()

            except Exception as e:
                error_count += 1
                frappe.log_error(f"Error processing client {ceipal_id}: {e}", "CEIPAL Client Sync Error")
                continue

        frappe.db.commit()

        next_page_url = api_data.get("next")

    final_msg = f"CEIPAL Sync Completed. Created: {created_count}, Updated: {updated_count}, Errors: {error_count}"
    frappe.logger("ceipal_client_sync").info(final_msg)
    return {"status": "success", "message": final_msg}
