// Mandate assignment dialog + dashboard for Job Opening.
// Uses server API for ToDo-backed rows so recruiters see correct totals and only their own row.

frappe.ui.form.on('Job Opening', {
	refresh(frm) {
		if (!frm.is_new()) {
			frm.remove_custom_button(__('Assign To'));

			frm.add_custom_button(__('Assign To'), () => {
				if (frm.is_dirty()) {
					frappe.msgprint(__("Please save the form before proceeding with assignments."));
					return;
				}
				open_bulk_assign_dialog(frm);
			}).addClass("btn-primary");

			render_assignment_dashboard(frm);
		}
	},

	validate: async function (frm) {
		if (frm.doc.job_title) {
			let base_route = frm.doc.job_title
				.toLowerCase()
				.replace(/[^a-z0-9]+/g, '-')
				.replace(/^-+|-+$/g, '');

			let route = base_route;
			let count = 1;

			while (true) {
				let result = await frappe.db.get_list('Job Opening', {
					filters: { route: route },
					fields: ['name'],
					limit: 1,
				});

				if (!result || result.length === 0) {
					break;
				}
				route = `${base_route}-${count}`;
				count++;
			}
			frm.set_value('route', route);
		}
	},
});

async function open_bulk_assign_dialog(frm) {
	let total_positions = frm.doc.custom_no_of_position || 0;

	let dialog = new frappe.ui.Dialog({
		title: __('Assign Positions to Recruiters'),
		size: 'large',
		fields: [{ fieldname: 'users_html', fieldtype: 'HTML' }],
		primary_action_label: __('Assign Now'),

		async primary_action() {
			let selected_data = [];
			let validation_failed = false;
			let any_user_exclusive = false;

			dialog.$wrapper.find('.user-row').each(function () {
				let is_checked = $(this).find('.user-check').is(':checked');
				let exclusivity_val = $(this).find('.exclusivity').val();
				if (is_checked && exclusivity_val === 'Yes') {
					any_user_exclusive = true;
				}
			});

			dialog.$wrapper.find('.user-row').each(function () {
				let checkbox = $(this).find('.user-check');
				let input = $(this).find('.position-input');
				let type = $(this).find('.recruiter-type-val').val();
				let exclusivity = $(this).find('.exclusivity').val() || 'No';
				let user = checkbox.val();

				if (checkbox.is(':checked')) {
					let positions = parseInt(input.val()) || 0;
					if (positions > total_positions) {
						frappe.msgprint(`User ${user}: Maximum ${total_positions} allowed.`);
						validation_failed = true;
						return false;
					}
					if (any_user_exclusive && exclusivity !== 'Yes') {
						frappe.msgprint(
							__(
								'A user is marked as Exclusive. You cannot assign positions to other non-exclusive users at the same time.'
							)
						);
						validation_failed = true;
						return false;
					}
					if (positions > 0) {
						selected_data.push({ user, positions, recruiter_type: type, exclusivity });
					}
				}
			});

			if (validation_failed) return;
			if (!selected_data.length) {
				frappe.msgprint('Please select at least one user and enter positions.');
				return;
			}

			frappe.dom.freeze('Processing Assignments...');

			try {
				for (let row of selected_data) {
					let existing = await frappe.db.get_list('ToDo', {
						fields: ['name'],
						filters: {
							reference_type: frm.doctype,
							reference_name: frm.doc.name,
							allocated_to: row.user,
							status: ['!=', 'Cancelled'],
						},
					});

					let todo_values = {
						custom_no_of_position: row.positions,
						recruiter_type: row.recruiter_type,
						exclusivity: row.exclusivity,
					};

					if (existing.length) {
						await frappe.db.set_value('ToDo', existing[0].name, todo_values);
					} else {
						await frappe.db.insert({
							doctype: 'ToDo',
							owner: row.user,
							allocated_to: row.user,
							reference_type: frm.doctype,
							reference_name: frm.doc.name,
							description: `Assigned mandate for ${frm.doc.job_title}`,
							status: 'Open',
							...todo_values,
						});
					}
				}

				frappe.show_alert({ message: __('Assigned Successfully'), indicator: 'green' });
				dialog.hide();
				frm.reload_doc();
			} catch (e) {
				console.error(e);
				frappe.msgprint(__('An error occurred during assignment.'));
			} finally {
				frappe.dom.unfreeze();
			}
		},
	});

	frappe.db
		.get_list('User', {
			fields: ['name', 'full_name', 'recruiter_type'],
			filters: { enabled: 1 },
			limit: 200,
		})
		.then((users) => {
			let html = `
        <div style="border-bottom: 2px solid #eee; padding: 10px; font-weight: bold; display: flex; background: #f8f9fa;">
            <div style="flex: 0.5;">Select</div>
            <div style="flex: 2;">Recruiter Name</div>
            <div style="flex: 1;">Positions</div>
            <div style="flex: 1;">Recruiter Type</div>
            <div style="flex: 1;">Exclusivity</div>
        </div>
        <div style="max-height:350px; overflow-y:auto;">`;

			users.forEach((u) => {
				let type_display = u.recruiter_type || '';
				html += `
            <div class="user-row" style="display:flex; align-items:center; gap:10px; padding: 10px; border-bottom: 1px solid #f1f1f1;">
                <div style="flex: 0.5;"><input type="checkbox" class="user-check" value="${u.name}"></div>
                <div style="flex: 2; font-size: 13px;">
                    <strong>${u.full_name || u.name}</strong><br><small style="color:gray;">${u.name}</small>
                </div>
                <div style="flex: 1;"><input type="number" class="position-input form-control" placeholder="0" style="width: 80%;"></div>
                <div style="flex: 1;">
                    <input type="hidden" class="recruiter-type-val" value="${type_display}">
                    <input type="text" class="form-control" value="${type_display}" readonly style="background-color: #f9f9f9;">
                </div>
                <div style="flex: 1;">
                    <select class="exclusivity form-control">
                        <option value="No">No</option>
                        <option value="Yes">Yes</option>
                    </select>
                </div>
            </div>`;
			});
			html += `</div>`;
			dialog.get_field('users_html').$wrapper.html(html);

			dialog.$wrapper.on('change', '.exclusivity', function () {
				let current_val = $(this).val();
				let $all_dropdowns = dialog.$wrapper.find('.exclusivity');
				if (current_val === 'Yes') {
					$all_dropdowns.not(this).prop('disabled', true).css('background-color', '#f1f1f1');
				} else {
					$all_dropdowns.prop('disabled', false).css('background-color', '');
				}
			});
		});
	dialog.show();
}

async function render_assignment_dashboard(frm) {
	const docname = frm.doc.name;

	let cv_counts = {};
	try {
		const r = await frappe.call({
			method: 'qbs_ats.qbs_ats.cv_count.get_cv_stats',
			args: { job_name: docname },
		});
		if (r && r.message) cv_counts = r.message;
	} catch (e) {
		console.error('CV Stats Error:', e);
	}

	let mandate_payload = {
		mandate_positions: frm.doc.custom_no_of_position || 0,
		total_assigned: 0,
		remaining: frm.doc.custom_no_of_position || 0,
		assignments: [],
	};
	try {
		const ar = await frappe.call({
			method: 'qbs_ats.qbs_ats.mandate_assignment.get_job_opening_mandate_assignments',
			args: { job_opening: docname },
		});
		if (ar && ar.message) {
			mandate_payload = ar.message;
		}
	} catch (e) {
		console.error('Mandate assignment API Error:', e);
	}

	const total_positions = mandate_payload.mandate_positions || 0;
	const total_assigned = mandate_payload.total_assigned || 0;
	const remaining = mandate_payload.remaining ?? Math.max(0, total_positions - total_assigned);
	const assignments = mandate_payload.assignments || [];

	let user_html = '';
	assignments.forEach((row) => {
		const user = row.user;
		const count = row.positions || 0;
		const label = frappe.utils.escape_html(row.full_name || user);
		const sub = frappe.utils.escape_html(user);
		user_html += `
        <div class="ats-recruiter-row" style="display:flex; justify-content:space-between; align-items:center; padding:12px; background:white; border-radius:10px; margin-bottom:10px; border:1px solid #e2e8f0;">
            <div style="flex:2;">
                <div style="font-weight:700;">${label}</div>
                <div style="font-size:11px; color:#718096;">${sub}</div>
            </div>
            <div style="flex:1; text-align:center;">
                <span style="background:#f0fff4; color:#22543d; padding:4px 12px; border-radius:99px; font-size:11px; font-weight:700; border:1px solid #c6f6d5;">
                    ${count} Assigned
                </span>
            </div>
            <div style="text-align:right;">
                <button type="button" class="btn btn-xs btn-primary ats-cv-parse-btn" data-recruiter="${frappe.utils.escape_html(
			user
		)}">
                    CV Parse: ${cv_counts[user] || 0}
                </button>
            </div>
        </div>`;
	});

	const dashboard_html = `
        <div class="ats-dashboard-container" style="background:#f7fafc; padding:20px; border-radius:16px; border:1px solid #e2e8f0; width: 100%;">
            <h5 style="margin-top:0;">📊 Mandate Performance Tracking</h5>
            <div style="display:flex; gap:12px; margin: 15px 0;">
                <div style="flex:1; background:white; padding:15px; border-radius:12px; text-align:center; border:1px solid #edf2f7;">
                    <div style="color:#718096; font-size:12px;">Mandate</div>
                    <div style="font-size:20px; font-weight:800;">${total_positions}</div>
                </div>
                <div style="flex:1; background:white; padding:15px; border-radius:12px; text-align:center; border:1px solid #edf2f7;">
                    <div style="color:#718096; font-size:12px;">Assigned</div>
                    <div style="font-size:20px; font-weight:800; color:#48bb78;">${total_assigned}</div>
                </div>
                <div style="flex:1; background:white; padding:15px; border-radius:12px; text-align:center; border:1px solid #edf2f7;">
                    <div style="color:#718096; font-size:12px;">Remaining</div>
                    <div style="font-size:20px; font-weight:800; color:#f56565;">${remaining}</div>
                </div>
            </div>
            ${
				user_html ||
				'<div style="text-align:center; color:#718096; padding:10px;">No recruiters assigned yet.</div>'
			}
        </div>
    `;

	if ($('.ats-dashboard-container').length > 0) {
		$('.ats-dashboard-container').parent().html(dashboard_html);
	} else {
		frm.dashboard.set_headline(dashboard_html);
	}

	$('.ats-dashboard-container')
		.off('click', '.ats-cv-parse-btn')
		.on('click', '.ats-cv-parse-btn', function () {
			const recruiter = $(this).data('recruiter');
			frappe.set_route('List', 'Job Applicant', { job_title: docname, custom_recruiter: recruiter });
		});
}
