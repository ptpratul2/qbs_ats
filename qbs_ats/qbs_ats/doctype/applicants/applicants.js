// Copyright (c) 2025
// Custom Script for Applicants Doctype

frappe.ui.form.on("Applicants", {
    refresh: function(frm) {
        beautify_applicants_form(frm);
        make_email_clickable(frm, "email_address");
        make_phone_clickable(frm, "mobile_number");
    },
    onload_post_render: function(frm) {
        beautify_applicants_form(frm);
    },
    after_save: function(frm) {
        beautify_applicants_form(frm);
    },
    on_submit: function(frm) {
        beautify_applicants_form(frm);
    }
});

// Make Email Clickable
function make_email_clickable(frm, fieldname) {
    const value = frm.doc[fieldname];
    if (!value) return;

    const $wrapper = $(frm.fields_dict[fieldname].wrapper);
    if ($wrapper.find(".control-value").length) {
        $wrapper.find(".control-value").html(
            `<a href="mailto:${value}" 
                style="font-size:12px; color:#0d6efd; text-decoration:underline;">
                ${value}
            </a>`
        );
    }
}

// Make Phone Clickable
function make_phone_clickable(frm, fieldname) {
    const value = frm.doc[fieldname];
    if (!value) return;

    const $wrapper = $(frm.fields_dict[fieldname].wrapper);
    if ($wrapper.find(".control-value").length) {
        $wrapper.find(".control-value").html(
            `<a href="tel:${value}" 
                style="font-size:12px; color:#16a085; text-decoration:underline;">
                ${value}
            </a>`
        );
    }
}

// Beautify Form
function beautify_applicants_form(frm) {
    const wrapper = frm.$wrapper;

    // Fields to apply properties (skip select fields)
    const fields = [
        "applicant_id",
        "last_name",
        "email_address",
        "mobile_number",
        "work_authorization",
        "address",
        "created_by",
        "created_on",
        "country",
        "state",
        "city",
        "source",
        "applicant_status",
        "job_title",
        "skills"
    ];

    // Apply properties only on input/text fields
    fields.forEach(field => {
        frm.set_df_property(field, "hidden", 0);
        frm.set_df_property(field, "read_only", 0);
        frm.set_df_property(field, "depends_on", "");
        frm.set_df_property(field, "description", "");
    });

    // Make required fields
    ["applicant_id", "last_name", "email_address", "mobile_number"].forEach(field => {
        frm.set_df_property(field, "reqd", 1);
    });

    // Form page styling
    wrapper.find(".form-page").css({
        "background": "#f9fbff",
        "border-radius": "14px",
        "padding": "30px",
        "box-shadow": "0 8px 20px rgba(0,0,0,0.05)",
        "margin": "20px auto",
        "font-family": "'Inter', sans-serif"
    });

    // Labels styling
    wrapper.find(".form-label").css({
        "font-weight": "600",
        "color": "#2c3e50",
        "font-size": "14px",
        "margin-bottom": "6px",
        "display": "block"
    });

    // Input and Textarea fields styling (exclude select)
    wrapper.find("input.input-with-feedback, textarea.form-control").css({
        "border": "1px solid #d6e0f0",
        "border-radius": "10px",
        "padding": "12px 14px",
        "font-size": "14px",
        "background": "#ffffff",
        "color": "#2c3e50",
        "box-shadow": "0 2px 6px rgba(0,0,0,0.03)",
        "transition": "0.3s ease"
    });

    wrapper.find("input.input-with-feedback, textarea.form-control").hover(function() {
        $(this).css("border-color", "#5dade2");
    }, function() {
        $(this).css("border-color", "#d6e0f0");
    });

    wrapper.find("input.input-with-feedback, textarea.form-control").focus(function() {
        $(this).css({
            "border-color": "#2980b9",
            "box-shadow": "0 0 6px rgba(41,128,185,0.3)"
        });
    }).blur(function() {
        $(this).css({
            "border-color": "#d6e0f0",
            "box-shadow": "0 2px 6px rgba(0,0,0,0.03)"
        });
    });

    // Section headings styling
    wrapper.find(".section-head, .form-section .form-section-heading").css({
        "background": "linear-gradient(90deg, #2980b9, #6dd5fa)",
        "color": "white",
        "padding": "12px 16px",
        "border-radius": "8px",
        "margin": "20px 0 14px",
        "font-weight": "600",
        "font-size": "15px",
        "letter-spacing": "0.5px",
        "text-transform": "uppercase",
        "box-shadow": "0 3px 8px rgba(0,0,0,0.08)"
    });

    // Buttons styling
    wrapper.find(".btn").css({
        "border-radius": "8px",
        "padding": "10px 18px",
        "font-weight": "600",
        "box-shadow": "0 3px 8px rgba(0,0,0,0.1)",
        "transition": "0.3s ease",
        "width": "100%"
    });

    wrapper.find(".btn-primary").css({
        "background": "linear-gradient(90deg, #2980b9, #6dd5fa)",
        "border": "none"
    }).hover(function() {
        $(this).css("opacity", "0.9");
    }, function() {
        $(this).css("opacity", "1");
    });

    wrapper.find(".btn-default").css({
        "background": "#ecf0f1",
        "border": "none"
    }).hover(function() {
        $(this).css("background", "#d0d7de");
    }, function() {
        $(this).css("background", "#ecf0f1");
    });
}
