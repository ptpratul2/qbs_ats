# Copyright (c) 2025, Prompt Personnel and contributors
# For license information, please see license.txt

import frappe
import requests
from frappe.model.document import Document
from qbs_ats.qbs_ats.doctype.job_creation.job_creation import get_active_token, generate_ceipal_token

class Vendor(Document):
    pass

CEIPAL_VENDORS_API = "https://api.ceipal.com/v1/getVendorsList?"

@frappe.whitelist()
def custom_method():
    """
    Fetches vendor data from the CEIPAL API and creates new Vendor documents in ERPNext.
    """
    print("Starting CEIPAL Vendor Sync Process...")

    token = get_active_token()
    if not token:
        print("No active token found. Generating a new CEIPAL token...")
        token_data = generate_ceipal_token()
        if not token_data or not token_data.get("access_token"):
            message = "Error: Could not generate a new CEIPAL token. Stopping sync."
            frappe.log_error(message, "CEIPAL Vendor Sync")
            return {"status": "error", "message": message}
        token = token_data.get("access_token")
        print("Successfully generated new token.")

    headers = {
        "Authorization": f"Bearer {token}",
    }

    try:
        print(f"Fetching vendors from CEIPAL API: {CEIPAL_VENDORS_API}")
        response = requests.get(CEIPAL_VENDORS_API, headers=headers)

        if response.status_code == 401:
            print("Token expired. Regenerating...")
            token_data = generate_ceipal_token()
            if not token_data or not token_data.get("access_token"):
                message = "Error: Could not regenerate CEIPAL token after expiry."
                frappe.log_error(message, "CEIPAL Vendor Sync")
                return {"status": "error", "message": message}
            token = token_data.get("access_token")
            headers["Authorization"] = f"Bearer {token}"
            response = requests.get(CEIPAL_VENDORS_API, headers=headers)

        response.raise_for_status()
        api_data = response.json()

        print("--- Raw API Response Received ---")
        print(api_data)
        print("---------------------------------")
        
        vendors_from_api = api_data.get('results', [])
        if not vendors_from_api:
            print("No vendor data found in the API response.")
            return {"status": "success", "message": "No vendors to sync."}
            
        created_count = 0
        skipped_count = 0

        for vendor_data in vendors_from_api:
            vendor_name = vendor_data.get('vendor_name')
            if not vendor_name:
                print(f"Skipping record due to missing vendor name. Data: {vendor_data}")
                continue

            print(f"\nProcessing Vendor: '{vendor_name}'")

            if frappe.db.exists("Vendor", {"vendor_name": vendor_name}):
                print(f"Vendor '{vendor_name}' already exists. Skipping.")
                skipped_count += 1
                continue

            try:
                new_vendor = {
                    "doctype": "Vendor",
                    "vendor_name": vendor_name,
                    "contact_number": vendor_data.get('contact_number'),
                    "website": vendor_data.get('website'),
                    "address": vendor_data.get('address'),
                    "country": vendor_data.get('country'),
                    "state": vendor_data.get('state'),
                    "city": vendor_data.get('city'),
                    "zip_code": vendor_data.get('zipcode'),
                    "created": vendor_data.get('created'),
                    "modified": vendor_data.get('modified'),
                    "primary_business_unit": vendor_data.get('primary_business_unit'),
                    "accessible_business_units": vendor_data.get('accessible_business_units'),
                    "primary_owner": vendor_data.get('primary_owner'),
                    "ownership": vendor_data.get('ownership'),
                    "created_by": vendor_data.get('created_by'),
                    "modified_by": vendor_data.get('modified_by')
                }

                print(f"Preparing to create new vendor with data: {new_vendor}")

                vendor_doc = frappe.get_doc(new_vendor)
                vendor_doc.insert(ignore_permissions=True)
                vendor_doc.submit()  

                created_count += 1
                print(f"Successfully created Vendor: '{vendor_name}'")

            except Exception as e:
                # Log any error that occurs during the document creation
                print(f"Error creating vendor '{vendor_name}'. Error: {e}")
                frappe.log_error(
                    f"Failed to create vendor: {vendor_name}\nData: {vendor_data}\nError: {e}",
                    "CEIPAL Vendor Sync"
                )

        frappe.db.commit()
        print("\n---------------------------------")
        print("CEIPAL Vendor Sync Finished.")
        final_message = f"Sync complete. Created: {created_count} vendors. Skipped: {skipped_count} (already existed)."
        print(final_message)
        print("---------------------------------")
        
        return {
            "status": "success", 
            "message": final_message,
            "created": created_count,
            "skipped": skipped_count
        }

    except requests.exceptions.RequestException as e:
        error_message = f"API request failed: {str(e)}"
        print(error_message)
        frappe.log_error(error_message, "CEIPAL Vendor Sync")
        return {"status": "error", "message": error_message}
    except Exception as e:
        error_message = f"An unexpected error occurred: {str(e)}"
        print(error_message)
        frappe.log_error(error_message, "CEIPAL Vendor Sync")
        return {"status": "error", "message": error_message}
