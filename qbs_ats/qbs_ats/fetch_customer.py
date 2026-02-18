import frappe
import requests
import json

def daily_fetch_crm_opportunities_and_sync():

    # print("\n" + "="*60)
    # print("CRM OPPORTUNITY → CLIENT SYNC STARTED")
    # print("="*60)

    crm_url = "https://crm.promptpersonnel.com/api/resource/Opportunity"

    headers = {
        "Authorization": f"token {frappe.conf.crm_api_key}:{frappe.conf.crm_api_secret}",
        "Content-Type": "application/json"
    }

    # Fields to fetch from CRM Opportunity
    opp_fields = [
        "name",
        "customer_name",
        "party_name",
        "custom_vertical",
        "status",
        "country",
        "state",
        "city",
        "custom_actual_revenue",
        "custom_open_mandates",
        "custom_requirement",
        "custom_closed_mandates",
        "custom_salary_range",
        "opportunity_owner",
        "opportunity_from",
        "source",
        "custom_client_status",
        "probability",
        "custom_expected_revenue_yearly",
        "industry",
        "transaction_date"
    ]

    # Conditions
    filters = [
        ["custom_vertical", "in", ["Permanent Staffing", "Temporary Staffing"]],
        ["status", "in", ["Closed Won", "Closed Lost"]]
    ]

    params = {
        "fields": json.dumps(opp_fields),
        "filters": json.dumps(filters),
        "limit_page_length": "None"
    }

    try:
        response = requests.get(crm_url, headers=headers, params=params, timeout=30)

        if response.status_code != 200:
            print("API ERROR:", response.text)
            return

        opportunities = response.json().get("data", [])
        # print("Total Opportunities Found:", len(opportunities))

        for opp in opportunities:

            crm_opp_id = opp.get("name")
            opportunity_name = opp.get("customer_name")

            print("\nProcessing:", crm_opp_id)

            if not opportunity_name:
                # print("No opportunity_name found, skipping")
                continue

            #  DUPLICATE CHECK BY opportunity_name
            if frappe.db.exists("Client", {"opportunity_name": opportunity_name}):
                print("Duplicate opportunity_name found, skipping")
                continue

            try:
                client = frappe.new_doc("Client")

                # Store CRM Opportunity ID (optional but recommended)
                client.crm_opportunity_id = crm_opp_id

                # -----------------------------
                # 1️ Location Section
                # -----------------------------
                client.country = opp.get("country")
                client.state = opp.get("state")
                client.city = opp.get("city")

                # -----------------------------
                # 2️ Requirements Section
                # -----------------------------
                client.actual_revenue = opp.get("custom_actual_revenue")
                client.open_mandates = opp.get("custom_open_mandates")
                client.requirements_details = opp.get("custom_requirement")
                client.closed_mandates = opp.get("custom_closed_mandates")
                client.salary_range = opp.get("custom_salary_range")

                # -----------------------------
                # 3️⃣ Opportunity Section
                # -----------------------------
                client.opportunity_name = opportunity_name
                client.vertical = opp.get("custom_vertical")
                client.opportunity_owner = opp.get("opportunity_owner")
                client.opportunity_from = opp.get("opportunity_from")
                client.industry = opp.get("industry")
                client.expected_close_date = opp.get("transaction_date")
                client.customer = opp.get("party_name")
                client.source = opp.get("source")
                client.client_status = opp.get("custom_client_status")
                client.probability_ = opp.get("probability")
                client.expected_revenue_yearly = opp.get("custom_expected_revenue_yearly")

                client.insert(ignore_permissions=True)

                print("Client Record Created ")

            except Exception as e:
                print("Insert Error:", str(e))
                frappe.log_error(
                    frappe.get_traceback(),
                    f"Client Sync Error: {crm_opp_id}"
                )

        frappe.db.commit()

        print("\nSYNC COMPLETED SUCCESSFULLY ")

    except Exception as e:
        print("GLOBAL ERROR:", str(e))
        frappe.log_error(
            frappe.get_traceback(),
            "Client Sync Fatal Error"
        )







def daily_fetch_crm_customers_and_sync():

    allowed_verticals = ["Permanent Staffing", "Temporary Staffing"]

    customer_url = "https://crm.promptpersonnel.com/api/resource/Customer"
    contact_url = "https://crm.promptpersonnel.com/api/resource/Contact"

    headers = {
        "Authorization": f"token {frappe.conf.crm_api_key}:{frappe.conf.crm_api_secret}",
        "Content-Type": "application/json"
    }

    page_length = 100
    start = 0

    total_customers_created = 0
    total_contacts_created = 0
    total_errors = 0

    while True:

        # STEP 1: FETCH CUSTOMERS

        customer_fields = [
            "name",
            "customer_name",
            "email_id",
            "mobile_no",
            "custom_vertical"
        ]

        params = {
            "fields": json.dumps(customer_fields),
            "filters": json.dumps([
                ["custom_vertical", "in", allowed_verticals]
            ]),
            "limit_start": start,
            "limit_page_length": page_length
        }

        try:
            cust_resp = requests.get(customer_url, headers=headers, params=params, timeout=30)

            if cust_resp.status_code != 200:
                frappe.log_error(cust_resp.text, "CRM Customer Fetch Error")
                break

            customers = cust_resp.json().get("data", [])

            if not customers:
                break

            print(f"\nFetched Customers Batch: {len(customers)}")

        except Exception:
            total_errors += 1
            frappe.log_error(frappe.get_traceback(), "CRM Customer Fetch Exception")
            break

        # STEP 2: CREATE CUSTOMER + FETCH CONTACTS

        for cust in customers:

            crm_customer_id = cust.get("name")
            if not crm_customer_id:
                continue

            try:

                #  Check if exists
                ats_customer_name = frappe.db.get_value(
                    "Customer",
                    {"custom_id": crm_customer_id},
                    "name"
                )

                #  If not exists, create
                if not ats_customer_name:

                    doc = frappe.new_doc("Customer")
                    doc.customer_name = cust.get("customer_name") or crm_customer_id
                    doc.customer_group = "All Customer Groups"
                    doc.territory = "All Territories"

                    doc.custom_id = crm_customer_id
                    doc.email_id = cust.get("email_id")
                    doc.mobile_no = cust.get("mobile_no")
                    doc.custom_vertical = cust.get("custom_vertical")

                    doc.insert(ignore_permissions=True)

                    ats_customer_name = doc.name
                    total_customers_created += 1

                    print(f" Customer Created: {ats_customer_name}")

                # STEP 3: FETCH CONTACTS FOR THIS CUSTOMER

                contact_start = 0

                while True:

                    contact_fields = [
                        "name",
                        "first_name",
                        "last_name",
                        "email_id",
                        "mobile_no"
                    ]

                    contact_params = {
                        "fields": json.dumps(contact_fields),
                        "filters": json.dumps([
                            ["Dynamic Link", "link_doctype", "=", "Customer"],
                            ["Dynamic Link", "link_name", "=", crm_customer_id]
                        ]),
                        "limit_start": contact_start,
                        "limit_page_length": 100
                    }

                    contact_resp = requests.get(
                        contact_url,
                        headers=headers,
                        params=contact_params,
                        timeout=30
                    )

                    if contact_resp.status_code != 200:
                        frappe.log_error(contact_resp.text, f"Contact Fetch Error {crm_customer_id}")
                        break

                    contacts = contact_resp.json().get("data", [])

                    if not contacts:
                        break

                    
                    for cont in contacts:

                        crm_contact_id = cont.get("name")
                        if not crm_contact_id:
                            continue

                        if frappe.db.exists("Contact", {"custom_id": crm_contact_id}):
                            continue

                        try:
                            contact_doc = frappe.new_doc("Contact")

                            contact_doc.first_name = cont.get("first_name") or crm_contact_id
                            contact_doc.last_name = cont.get("last_name")
                            contact_doc.custom_id = crm_contact_id

                            if cont.get("email_id"):
                                contact_doc.append("email_ids", {
                                    "email_id": cont.get("email_id"),
                                    "is_primary": 1
                                })

                            if cont.get("mobile_no"):
                                contact_doc.append("phone_nos", {
                                    "phone": cont.get("mobile_no"),
                                    "is_primary_mobile_no": 1
                                })

                            # 🔗 Proper Link with newly created/existing ATS customer
                            contact_doc.append("links", {
                                "link_doctype": "Customer",
                                "link_name": ats_customer_name
                            })

                            contact_doc.insert(ignore_permissions=True)

                            total_contacts_created += 1
                            print(f"   ➜ Contact Created: {contact_doc.name}")

                        except Exception:
                            total_errors += 1
                            frappe.log_error(
                                frappe.get_traceback(),
                                f"Contact Creation Error {crm_contact_id}"
                            )

                    frappe.db.commit()
                    contact_start += 100

            except Exception:
                total_errors += 1
                frappe.log_error(
                    frappe.get_traceback(),
                    f"Customer Processing Error {crm_customer_id}"
                )

        frappe.db.commit()
        start += page_length


    # print("Customers Created :", total_customers_created)
    # print("Contacts Created  :", total_contacts_created)
    # print("Total Errors      :", total_errors)
