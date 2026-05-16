import frappe
from frappe import _


def _user_sees_all_mandate_assignments(user: str | None = None) -> bool:
	user = user or frappe.session.user
	roles = frappe.get_roles(user)
	return "Administrator" in roles or "System Manager" in roles


@frappe.whitelist()
def get_job_opening_mandate_assignments(job_opening: str):
	"""Return mandate totals and per-recruiter position counts for the dashboard.

	- Administrator / System Manager: all assignment rows; totals are global.
	- Other users: only their own row in ``assignments``; totals stay global so
	  Mandate / Assigned / Remaining match the real mandate (requires server-side
	  ToDo read because ``frappe.db.get_list`` on the client respects ToDo rules).
	"""
	if not job_opening:
		frappe.throw(_("Job Opening not specified"))

	if not frappe.has_permission("Job Opening", "read", doc=job_opening):
		frappe.throw(_("Not permitted"), frappe.PermissionError)

	mandate = frappe.db.get_value("Job Opening", job_opening, "custom_no_of_position") or 0

	todos = frappe.get_all(
		"ToDo",
		fields=["allocated_to", "custom_no_of_position"],
		filters={
			"reference_type": "Job Opening",
			"reference_name": job_opening,
			"status": ["!=", "Cancelled"],
		},
		ignore_permissions=True,
	)

	user_totals: dict[str, int] = {}
	total_assigned = 0
	for row in todos:
		positions = row.get("custom_no_of_position") or 0
		total_assigned += positions
		allocated = row.get("allocated_to")
		if not allocated:
			continue
		user_totals[allocated] = user_totals.get(allocated, 0) + positions

	remaining = max(0, mandate - total_assigned)
	session_user = frappe.session.user

	if _user_sees_all_mandate_assignments():
		display_totals = dict(user_totals)
	else:
		my_count = user_totals.get(session_user, 0)
		display_totals = {session_user: my_count} if my_count else {}

	names = list(display_totals.keys())
	full_name_by_user = {}
	if names:
		for u in frappe.get_all("User", fields=["name", "full_name"], filters={"name": ["in", names]}):
			full_name_by_user[u.name] = u.full_name or u.name

	assignments = [
		{
			"user": user_id,
			"positions": display_totals[user_id],
			"full_name": full_name_by_user.get(user_id, user_id),
		}
		for user_id in sorted(display_totals.keys())
	]

	return {
		"mandate_positions": mandate,
		"total_assigned": total_assigned,
		"remaining": remaining,
		"assignments": assignments,
	}
