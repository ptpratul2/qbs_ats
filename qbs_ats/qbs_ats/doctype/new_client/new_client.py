# Copyright (c) 2025, Prompt Personnel and contributors
# For license information, please see license.txt

from frappe.model.document import Document
import frappe
import requests
from qbs_ats.qbs_ats.doctype.job_creation.job_creation import get_active_token, generate_ceipal_token

class NewClient(Document):
    pass

CEIPAL_CLIENT_API = "https://api.ceipal.com/v1/getClientsList?"

@frappe.whitelist()
def custom_method():
    """
    Fetches all clients from the paginated CEIPAL API and creates or updates them 
    in the 'New Client' DocType in ERPNext.
    """
    print(" custom_method() called for CEIPAL Client Sync")

    token = get_active_token()
    if not token:
        print(" No active token found. Generating a new one...")
        token_data = generate_ceipal_token()
        if not token_data or not token_data.get("access_token"):
            message = " Error: Could not generate a new CEIPAL token."
            frappe.log_error(message, "CEIPAL Client Sync")
            return {"status": "error", "message": message}
        token = token_data.get("access_token")
        print(" New token generated successfully.")

    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }

    try:
        created_count = 0
        updated_count = 0
        next_page_url = CEIPAL_CLIENT_API

        while next_page_url:
            print(f"📡 Fetching clients from URL: {next_page_url}")
            response = requests.get(next_page_url, headers=headers)

            if response.status_code == 401:
                print(" Token expired. Regenerating...")
                token_data = generate_ceipal_token()
                if not token_data or not token_data.get("access_token"):
                    message = " Error: Could not regenerate CEIPAL token."
                    frappe.log_error(message, "CEIPAL Client Sync")
                    return {"status": "error", "message": message}
                token = token_data.get("access_token")
                headers["Authorization"] = f"Bearer {token}"
                response = requests.get(next_page_url, headers=headers)

            response.raise_for_status()
            api_data = response.json()
            
            client_records = api_data.get("results", [])
            if not client_records:
                break

            print(f"Processing {len(client_records)} records from page {api_data.get('page_number')}...")

            for record in client_records:
                try:
                    ceipal_id = record.get('id')
                    if not ceipal_id:
                        print(f" Skipping record due to missing ID: {record.get('name')}")
                        continue

                    if frappe.db.exists("New Client", {"ceipal_client_id": ceipal_id}):
                        doc = frappe.get_doc("New Client", {"ceipal_client_id": ceipal_id})
                        updated_count += 1
                    else:
                        doc = frappe.new_doc("New Client")
                        doc.ceipal_client_id = ceipal_id
                        created_count += 1
                    
                    doc.client_name = record.get('name')
                    doc.website = record.get('website')
                    doc.country = record.get('country')
                    doc.state = record.get('state')
                    doc.city = record.get('city')
                    doc.postal_code = record.get('zipcode')
                    doc.status = record.get('status')
                    doc.category = record.get('category')
                    doc.ownership = record.get('ownership')
                    doc.created_by = record.get('created_by')
                    doc.created_at = record.get('created_at')
                    doc.updated_at = record.get('updated_at')
                    doc.industry = record.get('industry_exp')
                    doc.primary_business_unit = record.get('primary_business_unit')
                    doc.accessible_business_units = record.get('accessible_business_units')
                    doc.created_on = record.get('created_on')
                    doc.modified_on = record.get('modified_on')
                    doc.modified_by = record.get('modified_by')
                    doc.contact_number = record.get("contact_number")

                    api_industry = record.get('industry_exp')
                    if api_industry and api_industry != '0':
                        normalized_industry = api_industry.replace(' - ', '-')

                        if normalized_industry == 'Oil Refining-Petroleum-Drilling':
                            normalized_industry = 'Oil Refining-Petroleum-Driling'
                        
                        doc.industry = normalized_industry

                    doc.save(ignore_permissions=True)
                    doc.submit()

                except Exception as e:
                    error_msg = f"Error for '{record.get('name')}': {str(e)[:100]}"
                    print(f" {error_msg}")
                    frappe.log_error(title=error_msg, message="CEIPAL Client Sync Error")
            
            next_page_url = api_data.get('next')

        frappe.db.commit()
        
        success_message = f" Sync Complete! Created: {created_count}, Updated: {updated_count} clients."
        print(success_message)
        return {"status": "success", "message": success_message}

    except requests.exceptions.RequestException as e:
        error_msg = f" API request failed: {str(e)}"
        print(error_msg)
        frappe.log_error(title=error_msg, message="CEIPAL Client Sync")
        return {"status": "error", "message": error_msg}
    except Exception as e:
        error_msg = f"An unexpected error occurred: {str(e)}"
        print(error_msg)
        frappe.log_error(title=error_msg, message="CEIPAL Client Sync")
        return {"status": "error", "message": error_msg}
