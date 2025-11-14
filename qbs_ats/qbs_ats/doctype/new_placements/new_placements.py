import frappe
from frappe.model.document import Document
import requests
from requests.adapters import HTTPAdapter
from requests.packages.urllib3.util.retry import Retry
from qbs_ats.qbs_ats.doctype.job_creation.job_creation import get_active_token, generate_ceipal_token


# CEIPAL APIs
CEIPAL_PLACEMENTS_LIST_API = "https://api.ceipal.com/v1/getPlacementsList?"
CEIPAL_PLACEMENT_DETAIL_API = "https://api.ceipal.com/v1/getPlacementDetails/?placement_id="

class NewPlacements(Document):
    pass

def requests_session():
    """Configures a requests session with retries for robustness."""
    session = requests.Session()
    retries = Retry(
        total=5,
        backoff_factor=2,
        status_forcelist=[403, 429, 500, 502, 503, 504],
        allowed_methods=["GET", "POST"]
    )
    adapter = HTTPAdapter(max_retries=retries)
    session.mount("http://", adapter)
    session.mount("https://", adapter)
    return session

@frappe.whitelist()
def custom_method(batch_size=50, start_page=1, max_pages=None):
    """
    Syncs placement data from CEIPAL to Frappe's 'New Placements' DocType.

    Args:
        batch_size (int): Number of placements to fetch per page from CEIPAL.
        start_page (int): The page number to start fetching from.
        max_pages (int, optional): Maximum number of pages to process. If None, processes all pages.
    """
    print(" Starting CEIPAL Placements Sync...")
    frappe.logger("ceipal_placements_sync").info("Starting CEIPAL Placements Sync...")

    token = get_active_token()
    if not token:
        print(" No active token found. Generating new CEIPAL token...")
        token_data = generate_ceipal_token()
        if not token_data or not token_data.get("access_token"):
            frappe.logger("ceipal_placements_sync").error("Failed to generate CEIPAL token", exc_info=True)
            return {"status": "error", "message": "Failed to generate CEIPAL token"}
        token = token_data.get("access_token")
        print(" New CEIPAL token generated.")

    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    session = requests_session()

    created_count = 0
    updated_count = 0
    skipped_count = 0
    page = start_page
    has_more = True

    while has_more:
        if max_pages and page > max_pages:
            print(f" Reached maximum pages ({max_pages}). Ending sync.")
            frappe.logger("ceipal_placements_sync").info(f"Reached maximum pages ({max_pages}). Ending sync.")
            break

        list_url = f"{CEIPAL_PLACEMENTS_LIST_API}page={page}&limit={batch_size}"
        print(f"\n Fetching Placements List API (Page {page}, Limit {batch_size}): {list_url}")
        frappe.logger("ceipal_placements_sync").info(f"Fetching Placements List API (Page {page}): {list_url}")

        try:
            list_res = session.get(list_url, headers=headers, timeout=30)
            if list_res.status_code in [401, 403]:
                print(" Token expired or unauthorized for list API. Re-generating token...")
                frappe.logger("ceipal_placements_sync").info("Token expired or unauthorized. Generating new token...")
                token_data = generate_ceipal_token()
                if not token_data or not token_data.get("access_token"):
                    frappe.logger("ceipal_placements_sync").error("Failed to re-generate CEIPAL token after 401/403 for list API.", exc_info=True)
                    has_more = False
                    break # Exit loop if token refresh fails
                token = token_data.get("access_token")
                headers["Authorization"] = f"Bearer {token}"
                list_res = session.get(list_url, headers=headers, timeout=30) # Retry with new token
                print(" Token re-generated. Retrying list API call.")

            list_res.raise_for_status() # Raises HTTPError for bad responses (4xx or 5xx)
            list_data = list_res.json()
            placements_list = list_data.get("results") or list_data.get("placements") or []
            print(f"Successfully fetched {len(placements_list)} placements for page {page}.")
            # Using debug for full list data, info for summary
            frappe.logger("ceipal_placements_sync").debug(f"List API Data for page {page}: {placements_list}")

        except requests.exceptions.RequestException as e:
            frappe.logger("ceipal_placements_sync").error(f"HTTP error fetching placements list on page {page}: {e}", exc_info=True)
            return {"status": "error", "message": f"HTTP error fetching list on page {page}: {e}"}
        except Exception as e:
            frappe.logger("ceipal_placements_sync").error(f"An unexpected error occurred while fetching placements list on page {page}: {e}", exc_info=True)
            return {"status": "error", "message": f"Unexpected error fetching list on page {page}: {e}"}

        if not placements_list:
            print(f"No new placements found for page {page}. Ending sync.")
            frappe.logger("ceipal_placements_sync").info(f"No placements found for page {page}. Ending sync.")
            has_more = False
            break

        print(f" Processing {len(placements_list)} placements from page {page}...")
        for i, record in enumerate(placements_list):
            placement_id = record.get("placements_id") or record.get("id") or record.get("placement_id")
            
            if not placement_id:
                skipped_count += 1
                frappe.logger("ceipal_placements_sync").warning(f"Skipping record {i+1} on page {page} due to missing placement_id in list API record: {record}")
                print(f"Skipping record {i+1} on page {page}: Missing placement_id.")
                continue

            print(f"\n--- Processing Placement ID: {placement_id} ({i+1}/{len(placements_list)}) ---")
            frappe.logger("ceipal_placements_sync").info(f"Processing placement_id from list: {placement_id}")

            try:
                detail_url = f"{CEIPAL_PLACEMENT_DETAIL_API}{placement_id}"
                print(f" Fetching Detail API Data for Placement ID {placement_id}: {detail_url}")
                detail_res = session.get(detail_url, headers=headers, timeout=30)
                
                if detail_res.status_code in [401, 403]:
                    print(f" Token expired or unauthorized for detail API for {placement_id}. Re-generating token...")
                    frappe.logger("ceipal_placements_sync").info(f"Token expired or unauthorized for detail API for {placement_id}. Re-generating token...")
                    token_data = generate_ceipal_token()
                    if not token_data or not token_data.get("access_token"):
                        frappe.logger("ceipal_placements_sync").error(f"Failed to re-generate CEIPAL token for detail API for {placement_id}", exc_info=True)
                        skipped_count += 1
                        print(f" Failed to re-generate token for {placement_id}. Skipping.")
                        continue 
                    token = token_data.get("access_token")
                    headers["Authorization"] = f"Bearer {token}"
                    detail_res = session.get(detail_url, headers=headers, timeout=30) # Retry with new token
                    print(f" Token re-generated. Retrying detail API call for {placement_id}.")

                detail_res.raise_for_status()
                placement_info = detail_res.json()
                print(f" Successfully fetched detail data for {placement_id}.")
                frappe.logger("ceipal_placements_sync").debug(f"Detail API Data for Placement ID {placement_id}:\n{placement_info}")

                existing_doc_name = None
                try:
                    # IMPORTANT: 'placements_id' must be the exact field name in your Frappe DocType
                    existing_doc_name = frappe.db.get_value(
                        "New Placements",
                        {"placements_id": placement_id}, 
                        "name"
                    )
                except Exception as e:
                    frappe.logger("ceipal_placements_sync").error(f"Error checking for existing document for placement_id {placement_id}: {e}", exc_info=True)
                    pass 

               
                erpnext_data = {
                    "placements_id": placement_id, 
                    "client_name": placement_info.get("client_details", [{}])[0].get("client_name") if placement_info.get("client_details") else "",
                    "job_start_date": placement_info.get("placement_details", [{}])[0].get("job_start_date") if placement_info.get("placement_details") else None,
                    "job_end_date": placement_info.get("placement_details", [{}])[0].get("job_end_date") if placement_info.get("placement_details") else None,
                    "revenue_type": placement_info.get("revenue_type") or "",
                    "employee_name": placement_info.get("employee_name") or record.get("employee_name") or "",
                    "employee_number": placement_info.get("employee_number") or record.get("employee_number") or "",
                    "email": placement_info.get("email") or record.get("email") or "",
                    "placements_status": placement_info.get("placement_status") or "",
                    "is_confirmation": placement_info.get("is_confirmation"),
                    "business_unit_id": placement_info.get("business_unit_id"),
                    "created": placement_info.get("created") or "", 
                    "modified1": placement_info.get("modified") or "", 
                    "placement_status":placement_info.get("placement_status")
                }

                if existing_doc_name:
                    try:
                        placements_doc = frappe.get_doc("New Placements", existing_doc_name)
                        print(f" Updating existing placement Doc: {placements_doc.name} for {placement_id}")
                        frappe.logger("ceipal_placements_sync").info(f"Updating existing placement Doc: {placements_doc.name} for {placement_id}")
                        
                        placements_doc.update(erpnext_data)
                        
                        for table_field in ["payment_details", "client_details", "end_client_details", "supplier_details", "work_location", "placement_details"]:
                            placements_doc.set(table_field, [])
                        
                        updated_count += 1
                    except Exception as e:
                        frappe.logger("ceipal_placements_sync").error(f"Error updating existing document {existing_doc_name} for placement_id {placement_id}: {e}", exc_info=True)
                        skipped_count += 1
                        print(f" Error updating existing document {placement_id}. Skipping.")
                        continue 
                else:
                    try:
                        placements_doc = frappe.new_doc("New Placements")
                        print(f"Creating new placement Doc for {placement_id}")
                        frappe.logger("ceipal_placements_sync").info(f"Creating new placement Doc for {placement_id}")
                        placements_doc.update(erpnext_data)
                        created_count += 1
                    except Exception as e:
                        frappe.logger("ceipal_placements_sync").error(f"Error creating new document for placement_id {placement_id}: {e}", exc_info=True)
                        skipped_count += 1
                        print(f" Error creating new document for {placement_id}. Skipping.")
                        continue 

                child_tables_map = {
                    "payment_details": {"api_key": "payment_details", "fields_map": {
                        "employee_type": "employee_type", "payment_terms": "payment_terms", 
                        "gross_salary_annum": "gross_salary_annum", "fee_type": "fee_type",
                        "placement_fees": "placement_fees", "revenue_type": "revenue_type",
                        "purchase_order": "purchase_order", "currency": "currency"
                    }},
                    "client_details": {"api_key": "client_details", "fields_map": {
                        "client_manager": "client_manager", "client_email_id": "client_email_id",
                        "client_contactno": "client_contactno", "client_name": "client_name",
                        "address": "address", "country": "country", "state": "state", "city": "city"
                    }},
                    "end_client_details": {"api_key": "end_client", "fields_map": { # API has 'end_client', DocType has 'end_client_details'
                        "end_client_name": "end_client_name", "end_client_address": "end_client_address",
                        "end_client_country": "end_client_country", "end_client_state": "end_client_state",
                        "end_client_city": "end_client_city", "end_client_zip_code": "end_client_zip_code"
                    }},
                    "supplier_details": {"api_key": "supplier_details", "fields_map": {
                        "supplier_federal_id": "supplier_federal_id", "supplier_name": "supplier_name",
                        "supplier_contact_person": "supplier_contact_person", "supplier_mobile_no": "supplier_mobile_no",
                        "supplier_office_no": "supplier_office_no", "supplier_email": "supplier_email",
                        "supplier_addr": "supplier_addr", "supplier_country": "supplier_country",
                        "supplier_state": "supplier_state", "supplier_city": "supplier_city", # Corrected to 'city' here
                        "supplier_postal_code": "supplier_postal_code"
                    }},
                    "work_location": {"api_key": "work_location", "fields_map": {
                        "address": "address", "address2": "address2", "email_id": "email_id",
                        "country": "country", "state": "state", "city": "city",
                        "postal_code": "postal_code", "mobile_number": "mobile_number"
                    }},
                    "placement_details": {"api_key": "placement_details", "fields_map": {
                        "estimated_start_date": "estimated_start_date", "job_start_date": "job_start_date",
                        "job_scheduled_end_date": "job_scheduled_end_date", "job_end_date": "job_end_date",
                        "account_manager": "account_manager", "recruiter": "recruiter",
                        "sales_manager": "sales_manager", "new_account_manager": "new_account_manager"
                    }}
                }

                for child_doctype_fieldname, config in child_tables_map.items():
                    api_key = config["api_key"]
                    fields_map = config["fields_map"]
                    api_data_list = placement_info.get(api_key, [])

                    for item in api_data_list:
                        try:
                            child_row_data = {}
                            for doc_field, api_field in fields_map.items():
                                value = item.get(api_field)
                                if doc_field in ["estimated_start_date", "job_start_date", "job_scheduled_end_date", "job_end_date"]:
                                    child_row_data[doc_field] = value if value else None
                                else:
                                    child_row_data[doc_field] = value
                            
                            placements_doc.append(child_doctype_fieldname, child_row_data)
                        except Exception as e:
                            frappe.logger("ceipal_placements_sync").error(
                                f"Error populating child table '{child_doctype_fieldname}' for {placement_id}: {e}\nItem data: {item}", 
                                exc_info=True
                            )
                            print(f" Error populating {child_doctype_fieldname} for {placement_id}. Item: {item}")


                try:
                    placements_doc.save(ignore_permissions=True)
                    print(f" Document '{placements_doc.name}' for placement_id {placement_id} saved.")
                    frappe.logger("ceipal_placements_sync").info(f"Document {placements_doc.name} saved successfully for placement_id {placement_id}")

                    # Attempt to submit only if it's in Draft (docstatus == 0)
                    if placements_doc.docstatus == 0: 
                        placements_doc.submit()
                        print(f" Document '{placements_doc.name}' for placement_id {placement_id} submitted.")
                        frappe.logger("ceipal_placements_sync").info(f"Document {placements_doc.name} submitted successfully for placement_id {placement_id}")
                    elif placements_doc.docstatus == 1: 
                        print(f" Document '{placements_doc.name}' for placement_id {placement_id} is already submitted. No re-submission.")
                        frappe.logger("ceipal_placements_sync").info(f"Document {placements_doc.name} for placement_id {placement_id} is already submitted. No re-submission.")
                    else: 
                        print(f" Document '{placements_doc.name}' for placement_id {placement_id} is in status {placements_doc.docstatus}. Not attempting submission.")
                        frappe.logger("ceipal_placements_sync").warning(f"Document {placements_doc.name} for placement_id {placement_id} is in status {placements_doc.docstatus}. Not attempting submission.")

                    frappe.db.commit() 
                    frappe.logger("ceipal_placements_sync").info(f"Database committed for placement_id {placement_id}")
                    print(f"COMMIT: Changes for {placement_id} committed to database.")

                except frappe.exceptions.ValidationError as e:
                    frappe.logger("ceipal_placements_sync").error(f"Validation Error saving/submitting placement {placement_id}: {e}\nDocument data: {placements_doc.as_dict()}", exc_info=True)
                    skipped_count += 1
                    print(f" Validation Error for {placement_id}: {e}")
                except Exception as e:
                    frappe.logger("ceipal_placements_sync").error(f"Critical error saving/submitting placement {placement_id}: {e}\nDocument data: {placements_doc.as_dict()}", exc_info=True)
                    skipped_count += 1
                    print(f" Critical error saving/submitting placement {placement_id}: {e}")

            except requests.exceptions.RequestException as e:
                frappe.logger("ceipal_placements_sync").error(f"HTTP error fetching detail for placement {placement_id}: {e}", exc_info=True)
                skipped_count += 1
                print(f" HTTP error fetching detail for {placement_id}: {e}")
            except Exception as e:
                frappe.logger("ceipal_placements_sync").error(f"Failed processing placement {placement_id}: {e}", exc_info=True)
                skipped_count += 1
                print(f" Failed processing placement {placement_id}: {e}")
        

        has_more = bool(list_data.get("next"))
        if has_more:
            page += 1
            print(f" Moving to next page: {page}")
            frappe.logger("ceipal_placements_sync").info(f"Moving to next page: {page}")
        else:
            print(" Reached the last page or 'next' key is false. Ending sync.")
            frappe.logger("ceipal_placements_sync").info("Reached the last page or 'next' key is false. Ending sync.")

    print(f"\n CEIPAL Placements Sync Completed. Created: {created_count}, Updated: {updated_count}, Skipped: {skipped_count}")
    frappe.logger("ceipal_placements_sync").info(f"CEIPAL Placements Sync Completed. Created: {created_count}, Updated: {updated_count}, Skipped: {skipped_count}")
    return {"status": "success", "created": created_count, "updated": updated_count, "skipped": skipped_count}