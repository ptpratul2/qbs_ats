frappe.ui.form.on("Opportunity", {
    setup: function(frm) {
        frm.selected_status_for_change = null;
    },

    refresh: (frm) => {
        let base_statuses = [
            "Introduction",
            "Discussion",
            "Proposal",
            "Negotiation",
            "Agreement"
        ];

        const current_status = frm.doc.status;
        let displayed_statuses = [...base_statuses];

        // Add "Closed" if not in a final state and not already "Closed"
        if (!["Closed Won", "Closed Lost", "Drop"].includes(current_status) && current_status !== "Closed") {
            displayed_statuses.push("Closed");
        }

        // Always include Closed Won/Lost/Drop if they are the current status
        if (current_status === "Closed Won") {
            displayed_statuses.push("Closed Won");
        } else if (current_status === "Closed Lost") {
            displayed_statuses.push("Closed Lost");
            // If current status is Closed Lost, remove 'Closed' and 'Drop' if they were added.
            displayed_statuses = displayed_statuses.filter(s => s !== "Closed" && s !== "Drop");
        } else if (current_status === "Drop") {
            displayed_statuses.push("Drop");
            // If current status is Drop, remove 'Closed' and 'Closed Lost' if they were added.
            displayed_statuses = displayed_statuses.filter(s => s !== "Closed" && s !== "Closed Lost");
        }
        
        // If current status is Closed, we should show it
        if (current_status === "Closed") {
            displayed_statuses.push("Closed");
        }


        // Ensure "Drop" is always the last IF not already in a specific closed state
        if (!["Closed Won", "Closed Lost", "Drop"].includes(current_status)) {
            if (!displayed_statuses.includes("Drop")) {
                 displayed_statuses.push("Drop");
            }
        }
        
        
        if (current_status === "Closed Won" && displayed_statuses.includes("Closed")) {
            displayed_statuses = displayed_statuses.filter(s => s !== "Closed");
            if(!displayed_statuses.includes("Drop")) displayed_statuses.push("Drop");
        }
        // This block needs to be refined for Closed Lost to remove 'Drop'
        if (current_status === "Closed Lost" && displayed_statuses.includes("Closed")) {
            displayed_statuses = displayed_statuses.filter(s => s !== "Closed");

            displayed_statuses = displayed_statuses.filter(s => s !== "Drop"); 
        }
        if (current_status === "Drop" && displayed_statuses.includes("Closed")) {
            displayed_statuses = displayed_statuses.filter(s => s !== "Closed");
        }
        
        // Remove Closed Won/Closed Lost from displayed_statuses if current status is not them
        if (current_status !== "Closed Won") {
            displayed_statuses = displayed_statuses.filter(s => s !== "Closed Won");
        }
        if (current_status !== "Closed Lost") {
            displayed_statuses = displayed_statuses.filter(s => s !== "Closed Lost");
        }
        
        // Final check to remove 'Drop' if the current status is either 'Closed Won' or 'Closed Lost'
        if (current_status === "Closed Won" || current_status === "Closed Lost") {
            displayed_statuses = displayed_statuses.filter(s => s !== "Drop");
        }


        // Button hide for final states
        const end_states = ["Closed Won", "Closed Lost", "Drop"];
        const show_mark_complete = !end_states.includes(current_status);

        let html = `
            <style>
                .custom-lead-header {
                    background-color: white;
                    padding: 20px;
                    border-radius: 8px;
                    border: 1px solid #e5e7eb;
                    box-shadow: 0 1px 3px rgba(0, 0, 0, 0.1);
                    margin-bottom: 20px;
                }
                .lead-title-bar {
                    display: flex;
                    align-items: center;
                    justify-content: space-between;
                    margin-bottom: 20px;
                }
                .lead-left-section {
                    display: flex;
                    align-items: center;
                }
                .lead-icon {
                    font-size: 16px;
                    color: white;
                    background-color: #10b981;
                    padding: 8px;
                    border-radius: 4px;
                    margin-right: 12px;
                    line-height: 1;
                }
                .lead-badge {
                    background-color: #dcfce7;
                    color: #166534;
                    padding: 4px 8px;
                    border-radius: 4px;
                    font-size: 12px;
                    font-weight: 600;
                    margin-right: 12px;
                }
                .lead-name {
                    font-size: 20px;
                    font-weight: 600;
                    color: #111827;
                }
                .lead-details-grid {
                    display: grid;
                    grid-template-columns: repeat(4, 1fr);
                    gap: 20px;
                    margin-bottom: 20px;
                }
                .detail-item {
                    display: flex;
                    flex-direction: column;
                }
                .detail-label {
                    font-size: 14px;
                    color: #6b7280;
                    margin-bottom: 4px;
                    font-weight: 500;
                }
                .detail-value {
                    font-size: 14px;
                    color: #111827;
                    font-weight: 600;
                }
                .funnel-progress-container {
                    display: flex;
                    width: 100%;
                    height: 50px;
                    margin: 20px 0;
                    position: relative;
                    background: white;
                }
                
                .funnel-segment {
                    display: flex;
                    align-items: center;
                    justify-content: center;
                    position: relative;
                    flex: 1;
                    height: 100%;
                    background: #e5e7eb;
                    color: #6b7280;
                    font-size: 14px;
                    font-weight: 600;
                    cursor: pointer;
                    transition: all 0.3s ease;
                    margin-right: 2px;
                }
                
                .funnel-segment:not(:last-child) {
                    clip-path: polygon(0% 0%, calc(100% - 20px) 0%, 100% 50%, calc(100% - 20px) 100%, 0% 100%, 20px 50%);
                }
                
                .funnel-segment:first-child {
                    clip-path: polygon(0% 0%, calc(100% - 20px) 0%, 100% 50%, calc(100% - 20px) 100%, 0% 100%);
                    border-radius: 6px 0 0 6px;
                }
                
                .funnel-segment:last-child {
                    clip-path: polygon(0% 0%, 100% 0%, 100% 100%, 0% 100%, 20px 50%);
                    border-radius: 0 6px 6px 0;
                    margin-right: 0;
                }
                
                .funnel-segment.completed {
                    background: #10b981;
                    color: white;
                    box-shadow: 0 2px 4px rgba(16, 185, 129, 0.3);
                }
                
                .funnel-segment.active {
                    background: #10b981;
                    color: white;
                    box-shadow: 0 2px 4px rgba(16, 185, 129, 0.3);
                }
                
                .funnel-segment.final-stage {
                    background: #e5e7eb;
                    color: #6b7280;
                    border: 1px solid #d1d5db;
                }
                .funnel-segment.closed-won-active {
                    background: #10b981;
                    color: white;
                    box-shadow: 0 2px 4px rgba(16, 185, 129, 0.3);
                }
                .funnel-segment.closed-lost-active,
                .funnel-segment.drop-active { 
                    background: #ef4444;
                    color: white;
                    box-shadow: 0 2px 4px rgba(239, 68, 68, 0.3);
                }
                 .funnel-segment.selected {
                    border: 2px solid #3b82f6;
                    transform: scale(1.02);
                }

                .mark-complete-btn {
                    background: linear-gradient(135deg, #3b82f6, #1d4ed8);
                    color: white;
                    text-align: center;
                    padding: 15px;
                    border-radius: 8px;
                    font-weight: 600;
                    cursor: pointer;
                    margin-top: 10px;
                    user-select: none;
                    transition: all 0.3s ease;
                    box-shadow: 0 2px 4px rgba(59, 130, 246, 0.3);
                }
                
                .mark-complete-btn:hover {
                    background: linear-gradient(135deg, #2563eb, #1e40af);
                    transform: translateY(-1px);
                    box-shadow: 0 4px 8px rgba(59, 130, 246, 0.4);
                }

                /* Custom styles for the confirmation dialog buttons */
                /* frappe.ui.Dialog uses btn-primary for primary and btn-secondary for secondary by default */
                .modal-footer .btn-primary.closed-won-btn {
                    background-color: #10b981 !important; /* Green */
                    border-color: #10b981 !important;
                    color: white !important; /* Ensure text is white */
                }
                .modal-footer .btn-primary.closed-won-btn:hover {
                    background-color: #059669 !important;
                    border-color: #059669 !important;
                }
                .modal-footer .btn-secondary.closed-lost-btn { /* Changed from .btn-default to .btn-secondary */
                    background-color: #ef4444 !important; /* Red */
                    border-color: #ef4444 !important;
                    color: white !important; /* Ensure text is white */
                }
                .modal-footer .btn-secondary.closed-lost-btn:hover { /* Changed from .btn-default to .btn-secondary */
                    background-color: #dc2626 !important;
                    border-color: #dc2626 !important;
                }

            </style>
            
            <div class="custom-lead-header">
                 <div class="lead-title-bar">
                     <div class="lead-left-section">
                         <div class="lead-icon">★</div>
                         <div class="lead-badge">Opportunity</div>
                         <div class="lead-name">${frm.doc.title || ""}</div>
                     </div>
                 </div>
                 <div class="lead-details-grid">
                      <div class="detail-item"><span class="detail-label">Account Name</span><span class="detail-value">${frm.doc.customer_name || "N/A"}</span></div>
                      <div class="detail-item"><span class="detail-label">Close Date</span><span class="detail-value">${frm.doc.transaction_date || "N/A"}</span></div>
                      <div class="detail-item"><span class="detail-label">Opportunity Owner</span><span class="detail-value">${frm.doc.opportunity_owner || "N/A"}</span></div>
                      <div class="detail-item"><span class="detail-label">Contact Number</span><span class="detail-value">${frm.doc.contact_no || "N/A"}</span></div>
                 </div>
            </div>

            <div class="funnel-progress-container">
        `;

        // Create a universal order for status comparison to determine 'completed' or 'final-stage'
        const universal_status_order = [
            "Introduction", "Discussion", "Proposal", "Negotiation", "Agreement",
            "Closed", "Closed Won", "Closed Lost", "Drop"
        ];
        const current_universal_index = universal_status_order.indexOf(current_status);


        // MAIN LOOP
        displayed_statuses.forEach((status, index) => {
            let segment_class = "";
            const segment_universal_index = universal_status_order.indexOf(status);

            if (segment_universal_index < current_universal_index) {
                segment_class = "completed";
            } else if (segment_universal_index === current_universal_index) {
                if (status === "Closed Won") segment_class = "closed-won-active";
                else if (status === "Closed Lost" || status === "Drop") segment_class = "closed-lost-active"; // Use red for Closed Lost and Drop
                else segment_class = "active";
            } else {
                segment_class = "final-stage";
            }
            
            // Override active class for Closed if current status is Closed
            if (status === "Closed" && current_status === "Closed") {
                segment_class = "active";
            }

            html += `
                <div class="funnel-segment ${segment_class}" data-status="${status}">
                    <span class="segment-text">${status}</span>
                </div>
            `;
        });

        html += `</div>`;

        html += `<div class="actions-container" style="text-align: center;">`;
        
        if (show_mark_complete) {
            html += `<div class="mark-complete-btn">✓ Mark Status as Complete</div>`;
        }

        html += `<div class="mark-complete-btn save-status-btn" style="display: none;">Save Status Change</div>`;
        html += `</div>`;

        frm.dashboard.clear_headline();
        frm.dashboard.set_headline(html);
    },

    after_save: function(frm) {
        frm.selected_status_for_change = null;
        frm.dashboard.refresh();
    }
});

if (!window._opportunity_funnel_handlers_bound) {
    window._opportunity_funnel_handlers_bound = true;
    
    // Function to show the custom Closed/Closed Won/Closed Lost dialog
    const showClosedOutcomeDialog = (frm_instance) => {
        let dialog = new frappe.ui.Dialog({
            title: __("Closed Outcome"),
            fields: [
                {
                    fieldtype: 'HTML',
                    fieldname: 'question',
                    options: `
                        <p>${__("Final outcome of this opportunity?")}</p>
                        <p>${__("Please select one of the options below.")}</p>
                    `
                }
            ],
            // Primary action button for "Closed Won"
            primary_action_label: __("Closed Won"),
            primary_action: () => {
                frm_instance.set_value("status", "Closed Won");
                frm_instance.save();
                dialog.hide();
            },
            // Secondary action button for "Closed Lost"
            secondary_action_label: __("Closed Lost"),
            secondary_action: () => {
                frm_instance.set_value("status", "Closed Lost");
                frm_instance.save();
                dialog.hide();
            }
        });
        dialog.show();
        // For frappe.ui.Dialog, the default buttons are .btn-primary and .btn-secondary
        setTimeout(() => {
            const modal_footer = dialog.$wrapper.find('.modal-footer');
            if (modal_footer.length) {
                modal_footer.find(".btn-primary").addClass("closed-won-btn"); 
                modal_footer.find(".btn-secondary").addClass("closed-lost-btn"); // IMPORTANT: Changed from .btn-default to .btn-secondary
            }
        }, 50); // Small delay to ensure buttons are rendered
    };


    $(document).on("click.opportunity_funnel", ".funnel-segment", function() {
        const clicked_status = $(this).data("status");
        const frm = cur_frm;

        if (clicked_status !== frm.doc.status) {
            // Special handling for "Closed" segment click
            if (clicked_status === "Closed") {
                showClosedOutcomeDialog(frm); // Call the new dialog function
            } else {
                frm.selected_status_for_change = clicked_status;
                $(".funnel-segment").removeClass("selected");
                $(this).addClass("selected");
                $(".save-status-btn").show();
                $(".mark-complete-btn:not(.save-status-btn)").hide();
            }
        } else {
            frm.selected_status_for_change = null;
            $(".funnel-segment").removeClass("selected");
            $(".save-status-btn").hide();

            const end_states = ["Closed Won", "Closed Lost", "Drop"];
            if (!end_states.includes(frm.doc.status)) {
                 $(".mark-complete-btn:not(.save-status-btn)").show();
            }
        }
    });

    $(document).on("click.opportunity_funnel", ".save-status-btn", function() {
        const frm = cur_frm;
        if (frm.selected_status_for_change) {
            frm.set_value("status", frm.selected_status_for_change);
            frm.save();
        }
    });

    $(document).on("click.opportunity_funnel", ".mark-complete-btn:not(.save-status-btn)", function(e) {
        e.preventDefault();
        e.stopImmediatePropagation();
        
        const frm = cur_frm;
        // Universal order for navigation, ensuring 'Closed' is processed before final outcomes
        const navigation_statuses = ["Introduction", "Discussion", "Proposal", "Negotiation", "Agreement", "Closed", "Drop"];
        const current_status_index = navigation_statuses.indexOf(frm.doc.status);
        const next_status_index = current_status_index + 1;

        if (next_status_index < navigation_statuses.length) {
            const current_status = frm.doc.status;
            const next_status = navigation_statuses[next_status_index];

            if (current_status === "Proposal" && !frm.doc.custom_proposal_document) {
                frappe.msgprint({
                    title: __("Missing Attachment"),
                    indicator: "red",
                    message: __("Please attach Proposal Document before advancing.")
                });
                return;
            }
            
            if (current_status === "Agreement" && !frm.doc.custom_agreement_attachment) {
                frappe.msgprint({
                    title: __("Missing Attachment"),
                    indicator: "red",
                    message: __("Please attach Agreement before advancing.")
                });
                return;
            }

            // Special handling for moving into "Closed" status
            if (next_status === "Closed") {
                showClosedOutcomeDialog(frm); // Call the new dialog function
            } else {
                frm.set_value("status", next_status);
                frm.save();
            }
        } else if (frm.doc.status === "Closed") {
            // If already in Closed and "Mark Status as Complete" is clicked,
            // prompt for Closed Won/Lost again
            showClosedOutcomeDialog(frm); // Call the new dialog function
        }
    });
}