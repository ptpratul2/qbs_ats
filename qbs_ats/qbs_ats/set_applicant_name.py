import frappe
from frappe import _
from hrms.hr.doctype.job_applicant.job_applicant import get_interviewers

@frappe.whitelist()
def custom_create_interview(doc, interview_round):
    import json

    if isinstance(doc, str):
        doc = json.loads(doc)
        doc = frappe.get_doc(doc)

    round_designation = frappe.db.get_value("Interview Round", interview_round, "designation")

    if round_designation and doc.designation and round_designation != doc.designation:
        frappe.throw(
            _("Interview Round {0} is only applicable for the Designation {1}").format(
                interview_round, round_designation
            )
        )

    interview = frappe.new_doc("Interview")
    interview.interview_round = interview_round
    interview.job_applicant = doc.name
    interview.designation = doc.designation
    interview.resume_link = doc.resume_link
    interview.job_opening = doc.job_title

    interview.custom_client_name = doc.custom__client_name
    interview.custom_applicant_name = doc.applicant_name

    interviewers = get_interviewers(interview_round)
    for d in interviewers:
        interview.append("interview_details", {"interviewer": d.interviewer})

    return interview