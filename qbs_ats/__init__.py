__version__ = "0.0.1"



import hrms.hr.doctype.job_applicant.job_applicant as job_applicant

from qbs_ats.qbs_ats.set_applicant_name import custom_create_interview

job_applicant.create_interview = custom_create_interview



def apply_overrides():
    
    try:
        from qbs_ats.qbs_ats.override_department import patch_department

        patch_department()
    except Exception:
        pass


apply_overrides()
