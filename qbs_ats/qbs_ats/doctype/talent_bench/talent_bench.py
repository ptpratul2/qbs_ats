import frappe
import requests
import os
from frappe.model.document import Document
from qbs_ats.qbs_ats.doctype.job_creation.job_creation import (
    get_active_token,
    generate_ceipal_token
)

class TalentBench(Document):
    pass

CEIPAL_BENCH_API = "https://api.ceipal.com/v1/getBenchList?"

@frappe.whitelist()
def custom_method():
    """
    Fetches bench talent data from CEIPAL API and inserts or updates it into
    the ERPNext TalentBench Doctype.
    """
    print("Starting CEIPAL TalentBench Sync Process...")

    token = get_active_token()
    if not token:
        print("No active token found. Generating a new CEIPAL token...")
        token_data = generate_ceipal_token()
        if not token_data or not token_data.get("access_token"):
            message = "Error: Could not generate a new CEIPAL token. Stopping sync."
            frappe.log_error(message, "CEIPAL TalentBench Sync")
            return {"status": "error", "message": message}
        token = token_data.get("access_token")
        print("Successfully generated new token.")

    headers = {
        "Authorization": f"Bearer {token}",
    }

    try:
        print(f"Fetching talent bench from CEIPAL API: {CEIPAL_BENCH_API}")
        response = requests.get(CEIPAL_BENCH_API, headers=headers)

        if response.status_code == 401:
            print("Token expired. Regenerating...")
            token_data = generate_ceipal_token()
            if not token_data or not token_data.get("access_token"):
                message = "Error: Could not regenerate CEIPAL token after expiry."
                frappe.log_error(message, "CEIPAL TalentBench Sync")
                return {"status": "error", "message": message}
            token = token_data.get("access_token")
            headers["Authorization"] = f"Bearer {token}"
            print("Retrying CEIPAL API call with new token...")
            response = requests.get(CEIPAL_BENCH_API, headers=headers)

        response.raise_for_status()
        api_data = response.json()

       
        if not api_data or not api_data.get("results"):
            print("No new talent data found in the API response or 'results' key is missing.")
            return {"status": "success", "message": "No new talent data found."}

        talent_records = api_data.get("results")
        created_count = 0
        updated_count = 0

        print(f"Found {len(talent_records)} records to process.")

        for record in talent_records:
            try:
                bench_id = record.get('bench_id')
                if not bench_id:
                    print(f"Skipping record due to missing bench_id for consultant: {record.get('consultant_name', 'N/A')}")
                    continue

                doc = None
                if frappe.db.exists("Talent Bench", {"ceipal_bench_id": bench_id}):
                    doc = frappe.get_doc("Talent Bench", {"ceipal_bench_id": bench_id})
                    print(f"Updating existing Talent Bench: {bench_id} - {record.get('consultant_name')}")
                    updated_count += 1
                else:
                    doc = frappe.new_doc("Talent Bench")
                    doc.ceipal_bench_id = bench_id  
                    print(f"Creating new Talent Bench: {bench_id} - {record.get('consultant_name')}")
                    created_count += 1

                doc.data_xfvu = record.get('firstname')
                doc.last_name = record.get('lastname')
                doc.middle_name = record.get('middlename')
                doc.consultant_name = record.get('consultant_name') 
                doc.email_address = record.get('email')
                doc.alternate_email_address = record.get('email_address_1') 
                doc.mobile_number = record.get('mobile_number')
                doc.other_phone = record.get('other_phone') 
                doc.address = record.get('address')
                doc.city = record.get('city')
                doc.state = record.get('state')
                doc.country = record.get('country')
                doc.skills = record.get('skills')
                doc.primary_skills = record.get('primary_skill') 
                doc.phone = record.get('phone')
                doc.alternative_phone = record.get('alternative_phone')
                doc.primary_skill = record.get('primary_skill')
                doc.work_authorization = record.get('work_authorization')

                resume_path = record.get('resume_path')
                if resume_path and os.path.exists(resume_path): 
                    try:
                        filename = os.path.basename(resume_path)
                        with open(resume_path, 'rb') as f:
                            file_content = f.read()

                        frappe.attach_file(
                            file_content=file_content,
                            file_name=filename,
                            doctype="Talent Bench", 
                            name=doc.name,          
                            is_private=1            
                        )
                        print(f"Attached resume '{filename}' to Talent Bench: {doc.name}")
                    except Exception as file_e:
                        print(f"Error attaching resume from '{resume_path}': {file_e}")
                        frappe.log_error(f"Error attaching resume for {doc.name}: {file_e}", "CEIPAL TalentBench Sync")
                elif resume_path:
                    print(f"Resume path provided but file not found: {resume_path}")
                else:
                    print("No resume path provided for this record.")

                doc.save(ignore_permissions=True)
                doc.submit()
                frappe.db.commit() 

            except Exception as e:
                error_message = f"Error processing record for {record.get('consultant_name', 'N/A')} (Bench ID: {bench_id}): {str(e)}"
                frappe.log_error(error_message, "CEIPAL TalentBench Sync")
                print(error_message)
                frappe.db.rollback()

        success_message = f"Sync Complete! Created: {created_count}, Updated: {updated_count}."
        print(success_message)
        return {"status": "success", "message": success_message}

    except requests.exceptions.RequestException as e:
        error_message = f"HTTP Request Error during CEIPAL TalentBench Sync: {str(e)}"
        frappe.log_error(error_message, "CEIPAL TalentBench Sync")
        print(error_message)
        return {"status": "error", "message": str(e)}

    except Exception as e:
        error_message = f"General Error during CEIPAL TalentBench Sync: {str(e)}"
        frappe.log_error(error_message, "CEIPAL TalentBench Sync")
        print(error_message)
        return {"status": "error", "message": str(e)}
