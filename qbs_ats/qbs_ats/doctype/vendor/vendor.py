
import frappe
import requests
from frappe.model.document import Document
from qbs_ats.qbs_ats.doctype.job_creation.job_creation import get_active_token, generate_ceipal_token

class Vendor(Document):
    pass

CEIPAL_VENDORS_API = "https://api.ceipal.com/v1/getVendorsList?"
CEIPAL_VENDOR_DETAIL_API = "https://api.ceipal.com/v1/getVendorDetails/?vendor_id="

@frappe.whitelist()
def custom_method():
    """
    Fetches vendor data from CEIPAL API and maps contact details to Vendor Contact Details child table.
    """
    print(" Starting CEIPAL Vendor Sync Process...")

    token = get_active_token()
    if not token:
        token_data = generate_ceipal_token()
        if not token_data or not token_data.get("access_token"):
            message = " Could not generate CEIPAL token. Stopping sync."
            frappe.log_error(message, "CEIPAL Vendor Sync")
            return {"status": "error", "message": message}
        token = token_data.get("access_token")

    headers = {"Authorization": f"Bearer {token}"}

    created_count = 0
    skipped_count = 0

    try:
        response = requests.get(CEIPAL_VENDORS_API, headers=headers, timeout=30)

        if response.status_code == 401:
            token_data = generate_ceipal_token()
            token = token_data.get("access_token")
            headers["Authorization"] = f"Bearer {token}"
            response = requests.get(CEIPAL_VENDORS_API, headers=headers, timeout=30)

        response.raise_for_status()
        vendors_from_api = response.json().get("results", [])

        if not vendors_from_api:
            return {"status": "success", "message": "No vendors to sync."}

        for vendor_data in vendors_from_api:
            vendor_id = vendor_data.get("id")
            vendor_name = vendor_data.get("vendor_name")

            if not vendor_id or not vendor_name:
                continue

            print(f"\n Vendor: {vendor_name} | ID: {vendor_id}")

            if frappe.db.exists("Vendor", {"vendor_name": vendor_name}):
                print(f"Vendor '{vendor_name}' already exists. Skipping.")
                skipped_count += 1
                continue

            detail_url = f"{CEIPAL_VENDOR_DETAIL_API}{vendor_id}"
            detail_res = requests.get(detail_url, headers=headers, timeout=30)
            detail_res.raise_for_status()
            detail_data = detail_res.json()

            vendor_doc = frappe.get_doc({
                "doctype": "Vendor",
                "vendor_name": vendor_name,
                "contact_number": vendor_data.get("contact_number"),
                "website": vendor_data.get("website"),
                "country": vendor_data.get("country"),
                "state": vendor_data.get("state"),
                "city": vendor_data.get("city"),
                "zip_code": vendor_data.get("zipcode"),
                "primary_business_unit": vendor_data.get("primary_business_unit"),
                "accessible_business_units": vendor_data.get("accessible_business_units"),
            })

            for c in detail_data.get("contacts", []):
                vendor_doc.append("vendor_contact_details", {
                    "first_name": c.get("first_name"),
                    "last_name": c.get("last_name"),
                    "designation": c.get("designation"),
                    "primary_owner": c.get("primary_owner"),
                    "work_phone": c.get("work_phone"),
                    "mobile": c.get("mobile"),
                    "eamil": c.get("email"),  
                    "address1": c.get("address1"),
                    "address2": c.get("address2"),
                    "country": c.get("country"),
                    "state": c.get("state"),
                    "city": c.get("city"),
                    "zip_code": c.get("zip_code"),
                    "vendor_contact_status": c.get("vendor_contact_status")
                })

            vendor_doc.insert(ignore_permissions=True)
            vendor_doc.submit()
            created_count += 1
            print(f" Vendor '{vendor_name}' created with {len(vendor_doc.vendor_contact_details)} contacts.")

        frappe.db.commit()
        print(f"\n CEIPAL Vendor Sync Completed. Created: {created_count}, Skipped: {skipped_count}")
        return {"status": "success", "created": created_count, "skipped": skipped_count}

    except requests.exceptions.RequestException as e:
        error_title = f"CEIPAL Vendor Sync Request Error: {str(e)[:120]}"
        error_message = f"Full exception: {str(e)}"
        frappe.log_error(title=error_title, message=error_message)
        return {"status": "error", "message": str(e)}

    except Exception as e:
        error_title = f"CEIPAL Vendor Sync Error: {str(e)[:120]}"
        error_message = f"Full exception: {str(e)}"
        frappe.log_error(title=error_title, message=error_message)
        return {"status": "error", "message": str(e)}
