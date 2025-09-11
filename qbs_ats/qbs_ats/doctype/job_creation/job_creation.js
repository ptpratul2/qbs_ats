// Copyright (c) 2025
// Custom Script for Job Creation Doctype

frappe.ui.form.on('Job Creation', {
    refresh: function(frm) {
        function make_field_clickable(fieldname) {
            const value = frm.doc[fieldname];
            if (!value) return;

            let href = value;
            if (!/^https?:\/\//i.test(href)) {
                href = 'https://' + href;
            }

            const $display = $(frm.fields_dict[fieldname].wrapper).find('.display-field');
            if ($display.length) {
                $display.html(
                    `<a href="${href}" target="_blank" 
                        style="font-size:12px; color:#0d6efd; text-decoration:underline;">
                        ${value}
                     </a>`
                );
            }
        }

        make_field_clickable('apply_job');
        make_field_clickable('apply_job_without_registration');

        let wrapper = frm.$wrapper;

        wrapper.find(".form-page").css({
            "background": "#f9fbff",
            "border-radius": "14px",
            "padding": "30px",
            "box-shadow": "0 8px 20px rgba(0,0,0,0.05)",
            "margin": "20px auto",
            "font-family": "'Inter', sans-serif"
        });

        wrapper.find(".form-label").css({
            "font-weight": "600",
            "color": "#34495e",
            "font-size": "14px",
            "margin-bottom": "6px",
            "display": "block"
        });

        wrapper.find(".form-control").hover(function() {
            $(this).css("border-color", "#5dade2");
        }, function() {
            $(this).css("border-color", "#d6e0f0");
        });

        wrapper.find(".form-control").focus(function() {
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

        wrapper.find(".section-head").css({
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

        wrapper.find(".btn").css({
            "border-radius": "8px",
            "padding": "10px 18px",
            "font-weight": "600",
            "box-shadow": "0 3px 8px rgba(0,0,0,0.1)",
            "transition": "0.3s ease"
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
});
