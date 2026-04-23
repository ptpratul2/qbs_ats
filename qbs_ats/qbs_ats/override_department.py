import importlib

import frappe

DEPARTMENT_MODULE = "erpnext.setup.doctype.department.department"

def patch_department():
    module = importlib.import_module(DEPARTMENT_MODULE)
    OriginalDepartment = module.Department

    class CustomDepartment(OriginalDepartment):
        def autoname(self):
            self.name = self.department_name

    module.Department = CustomDepartment

