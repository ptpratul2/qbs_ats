import frappe
import re


@frappe.whitelist()
def create_client_from_customer_v2(customers=None):

    selected_customers = frappe.db.get_list(
        "Customer",
        filters={"custom_vertical": ["in", ["Temporary Staffing", "Permanent Staffing"]]},
        pluck="name"
    )

    count = 0

    def clean_phone(phone_str):
        if not phone_str:
            return 0
        digits = "".join(filter(str.isdigit, str(phone_str)))
        return int(digits[:10]) if digits else 0

    for cust_name in selected_customers:
        try:
            customer_doc = frappe.get_doc("Customer", cust_name)

            # Check Closed Won opportunity
            closed_won_exist = frappe.db.exists(
                "Opportunity",
                {"customer_name": customer_doc.customer_name, "status": "Closed Won"}
            )

            if not closed_won_exist:
                continue

            # Duplicate check
            if frappe.db.exists("New Client", {"client_name": customer_doc.customer_name}):
                continue

            new_client = frappe.new_doc("New Client")

            # BASIC DETAILS
            new_client.client_name = customer_doc.customer_name
            new_client.website = customer_doc.website
            new_client.industry = customer_doc.industry
            new_client.status = "Active"
            new_client.vertical = customer_doc.custom_vertical

            # BUSINESS
            new_client.turnover_range = customer_doc.custom_turnover_in_inr
            new_client.nature_of_business = customer_doc.custom_nature_of_business
            new_client.lead_source = customer_doc.custom_lead_source

            # ADDRESS
            new_client.address_line_1 = customer_doc.custom_billing_street
            new_client.city = customer_doc.custom_billing_city
            new_client.state = customer_doc.custom_billing_stateprovince
            new_client.province = customer_doc.custom_billing_stateprovince
            new_client.country = customer_doc.custom_billing_country

            if customer_doc.custom_billing_zippostal_code:
                zip_clean = clean_phone(customer_doc.custom_billing_zippostal_code)
                new_client.zip_code = zip_clean
                new_client.postal_code = zip_clean

            phone_val = clean_phone(customer_doc.custom_phone)
            new_client.mobile_number = phone_val
            new_client.contact_number = phone_val

            # OWNER
            if customer_doc.account_manager:
                new_client.primary_owner = frappe.db.get_value(
                    "User", customer_doc.account_manager, "full_name"
                )

            # CONTACT
            contact_email = ""
            contact_name = "Manager"
            contact_mobile = phone_val

            primary_contact = frappe.db.get_value(
                "Dynamic Link",
                {"link_doctype": "Customer", "link_name": cust_name, "parenttype": "Contact"},
                "parent"
            )

            if primary_contact:
                contact_doc = frappe.get_doc("Contact", primary_contact)
                contact_email = contact_doc.email_id or ""
                contact_name = f"{contact_doc.first_name} {contact_doc.last_name or ''}".strip()
                if contact_doc.mobile_no:
                    contact_mobile = clean_phone(contact_doc.mobile_no)

            new_client.email_id = contact_email

            row = new_client.append("contact_details", {})
            row.first_name = contact_name
            row.email = contact_email
            row.mobile_no = contact_mobile

            new_client.insert(ignore_permissions=True)
            new_client.submit()

            count += 1

        except Exception as e:
            frappe.log_error(
                f"Error creating client {cust_name}: {str(e)}",
                "Customer Import Error"
            )

    return f"{count} Clients Successfully Imported!"





def create_client_on_opportunity(doc, method):
    """
    This function runs ONLY when Opportunity status becomes Closed Won.
    It creates New Client for the SAME customer linked in this Opportunity.
    """

    # Run only when status changed to Closed Won
    if doc.status != "Closed Won":
        return

    # Customer linked in Opportunity
    customer_name = doc.customer_name
    if not customer_name:
        return

    # Fetch Customer Document
    customer_doc = frappe.get_doc("Customer", customer_name)

    # Vertical Check (Required)
    if customer_doc.custom_vertical not in ["Temporary Staffing", "Permanent Staffing"]:
        return

    # Duplicate Check
    if frappe.db.exists("New Client", {"client_name": customer_doc.customer_name}):
        return

    # Helper function for phone cleaning
    def clean_phone(phone_str):
        if not phone_str:
            return 0
        digits = "".join(filter(str.isdigit, str(phone_str)))
        return int(digits[:10]) if digits else 0

    # Create New Client
    new_client = frappe.new_doc("New Client")

    # BASIC DETAILS
    new_client.client_name = customer_doc.customer_name
    new_client.website = customer_doc.website
    new_client.industry = customer_doc.industry
    new_client.status = "Active"
    new_client.vertical = customer_doc.custom_vertical

    # BUSINESS FIELDS
    new_client.turnover_range = customer_doc.custom_turnover_in_inr
    new_client.nature_of_business = customer_doc.custom_nature_of_business
    new_client.lead_source = customer_doc.custom_lead_source

    # ADDRESS DETAILS
    new_client.address_line_1 = customer_doc.custom_billing_street
    new_client.city = customer_doc.custom_billing_city
    new_client.state = customer_doc.custom_billing_stateprovince
    new_client.province = customer_doc.custom_billing_stateprovince
    new_client.country = customer_doc.custom_billing_country

    if customer_doc.custom_billing_zippostal_code:
        zip_clean = clean_phone(customer_doc.custom_billing_zippostal_code)
        new_client.zip_code = zip_clean
        new_client.postal_code = zip_clean

    # PHONE
    phone_val = clean_phone(customer_doc.custom_phone)
    new_client.mobile_number = phone_val
    new_client.contact_number = phone_val

    # OWNER
    if customer_doc.account_manager:
        new_client.primary_owner = frappe.db.get_value(
            "User", customer_doc.account_manager, "full_name"
        )

    # CONTACT DETAILS
    contact_email = ""
    contact_name = "Manager"
    contact_mobile = phone_val

    primary_contact = frappe.db.get_value(
        "Dynamic Link",
        {"link_doctype": "Customer", "link_name": customer_name, "parenttype": "Contact"},
        "parent"
    )

    if primary_contact:
        contact_doc = frappe.get_doc("Contact", primary_contact)
        contact_email = contact_doc.email_id or ""
        contact_name = f"{contact_doc.first_name} {contact_doc.last_name or ''}".strip()
        if contact_doc.mobile_no:
            contact_mobile = clean_phone(contact_doc.mobile_no)

    new_client.email_id = contact_email

    row = new_client.append("contact_details", {})
    row.first_name = contact_name
    row.email = contact_email
    row.mobile_no = contact_mobile

    # Save
    new_client.insert(ignore_permissions=True)
    new_client.submit()

    frappe.msgprint(f"New Client Created for Customer: {customer_name}")
