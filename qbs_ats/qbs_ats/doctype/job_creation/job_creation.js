// // Copyright (c) 2025
// // Custom Script for Job Creation Doctype

// frappe.ui.form.on('Job Creation', {
//     refresh: function(frm) {
//         function make_field_clickable(fieldname) {
//             const value = frm.doc[fieldname];
//             if (!value) return;

//             let href = value;
//             if (!/^https?:\/\//i.test(href)) {
//                 href = 'https://' + href;
//             }

//             const $display = $(frm.fields_dict[fieldname].wrapper).find('.display-field');
//             if ($display.length) {
//                 $display.html(
//                     `<a href="${href}" target="_blank" 
//                         style="font-size:12px; color:#0d6efd; text-decoration:underline;">
//                         ${value}
//                      </a>`
//                 );
//             }
//         }

//         make_field_clickable('apply_job');
//         make_field_clickable('apply_job_without_registration');

//         let wrapper = frm.$wrapper;

//         wrapper.find(".form-page").css({
//             "background": "#f9fbff",
//             "border-radius": "14px",
//             "padding": "30px",
//             "box-shadow": "0 8px 20px rgba(0,0,0,0.05)",
//             "margin": "20px auto",
//             "font-family": "'Inter', sans-serif"
//         });

//         wrapper.find(".form-label").css({
//             "font-weight": "600",
//             "color": "#34495e",
//             "font-size": "14px",
//             "margin-bottom": "6px",
//             "display": "block"
//         });

//         wrapper.find(".form-control").hover(function() {
//             $(this).css("border-color", "#5dade2");
//         }, function() {
//             $(this).css("border-color", "#d6e0f0");
//         });

//         wrapper.find(".form-control").focus(function() {
//             $(this).css({
//                 "border-color": "#2980b9",
//                 "box-shadow": "0 0 6px rgba(41,128,185,0.3)"
//             });
//         }).blur(function() {
//             $(this).css({
//                 "border-color": "#d6e0f0",
//                 "box-shadow": "0 2px 6px rgba(0,0,0,0.03)"
//             });
//         });

//         wrapper.find(".section-head").css({
//             "background": "linear-gradient(90deg, #2980b9, #6dd5fa)",
//             "color": "white",
//             "padding": "12px 16px",
//             "border-radius": "8px",
//             "margin": "20px 0 14px",
//             "font-weight": "600",
//             "font-size": "15px",
//             "letter-spacing": "0.5px",
//             "text-transform": "uppercase",
//             "box-shadow": "0 3px 8px rgba(0,0,0,0.08)"
//         });

//         wrapper.find(".btn").css({
//             "border-radius": "8px",
//             "padding": "10px 18px",
//             "font-weight": "600",
//             "box-shadow": "0 3px 8px rgba(0,0,0,0.1)",
//             "transition": "0.3s ease"
//         });

//         wrapper.find(".btn-primary").css({
//             "background": "linear-gradient(90deg, #2980b9, #6dd5fa)",
//             "border": "none"
//         }).hover(function() {
//             $(this).css("opacity", "0.9");
//         }, function() {
//             $(this).css("opacity", "1");
//         });

//         wrapper.find(".btn-default").css({
//             "background": "#ecf0f1",
//             "border": "none"
//         }).hover(function() {
//             $(this).css("background", "#d0d7de");
//         }, function() {
//             $(this).css("background", "#ecf0f1");
//         });
//     }
// });





// Copyright (c) 2025
// Custom Script for Job Creation Doctype

frappe.ui.form.on("Job Creation", {
    refresh: function(frm) {
        // ------------------------
        // 1. Make URL fields clickable
        // ------------------------
        function make_field_clickable(fieldname) {
            const value = frm.doc[fieldname];
            if (!value) return;

            let href = value;
            if (!/^https?:\/\//i.test(href)) {
                href = "https://" + href;
            }

            const $display = $(frm.fields_dict[fieldname].wrapper).find(".display-field");
            if ($display.length) {
                $display.html(
                    `<a href="${href}" target="_blank" 
                        style="font-size:12px; color:#0d6efd; text-decoration:underline;">
                        ${value}
                     </a>`
                );
            }
        }

        make_field_clickable("apply_job");
        make_field_clickable("apply_job_without_registration");

        // ------------------------
        // 2. UI Styling for Job Creation Form
        // ------------------------
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

        wrapper.find(".form-control").hover(
            function () {
                $(this).css("border-color", "#5dade2");
            },
            function () {
                $(this).css("border-color", "#d6e0f0");
            }
        );

        wrapper.find(".form-control")
            .focus(function () {
                $(this).css({
                    "border-color": "#2980b9",
                    "box-shadow": "0 0 6px rgba(41,128,185,0.3)"
                });
            })
            .blur(function () {
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
        }).hover(
            function () {
                $(this).css("opacity", "0.9");
            },
            function () {
                $(this).css("opacity", "1");
            }
        );

        wrapper.find(".btn-default").css({
            "background": "#ecf0f1",
            "border": "none"
        }).hover(
            function () {
                $(this).css("background", "#d0d7de");
            },
            function () {
                $(this).css("background", "#ecf0f1");
            }
        );

        // ------------------------
        // 3. Submission Dashboard Loader
        // ------------------------
        if (frm.fields_dict.submission_dashboard && frm.fields_dict.submission_dashboard.wrapper) {
            $(frm.fields_dict.submission_dashboard.wrapper).empty();
            $(frm.fields_dict.submission_dashboard.wrapper).html(dashboard_html_code(frm.doc.name));
        }
    }
});

// ------------------------
// 4. Dashboard HTML Builder
// ------------------------
function dashboard_html_code(job_id) {
    return `
<style>
.submission-dashboard {
  font-family: 'Inter', sans-serif;
  padding: 16px;
  background: #f8fafc;
  border-radius: 12px;
}
.submission-dashboard .controls {
  display: flex;
  gap: 12px;
  margin-bottom: 16px;
}
.submission-dashboard .controls input,
.submission-dashboard .controls select,
.submission-dashboard .controls button {
  padding: 8px 12px;
  border: 1px solid #cbd5e1;
  border-radius: 6px;
  font-size: 14px;
}
.submission-dashboard .summary {
  display: flex;
  gap: 12px;
  margin-bottom: 16px;
}
.submission-dashboard .summary-card {
  flex: 1;
  padding: 12px;
  border-radius: 8px;
  background: #fff;
  box-shadow: 0 1px 3px rgba(0,0,0,0.1);
  text-align: center;
}
.submission-dashboard table {
  width: 100%;
  border-collapse: collapse;
  background: #fff;
  border-radius: 8px;
  overflow: hidden;
}
.submission-dashboard th, 
.submission-dashboard td {
  padding: 10px;
  border: 1px solid #e2e8f0;
  text-align: left;
  font-size: 14px;
}
.submission-dashboard th {
  background: #f1f5f9;
  font-weight: 600;
}
.submission-dashboard .btn {
  padding: 6px 12px;
  font-size: 13px;
  border: none;
  border-radius: 6px;
  cursor: pointer;
}
.submission-dashboard .btn-open {
  background: #3b82f6;
  color: #fff;
}
.submission-dashboard .btn-resume {
  background: #10b981;
  color: #fff;
}
</style>

<div class="submission-dashboard">
  <div class="controls">
    <input type="text" id="searchBox" placeholder="Search Candidate...">
    <select id="statusFilter">
      <option value="">All Status</option>
      <option value="Submitted">Submitted</option>
      <option value="Interviewed">Interviewed</option>
      <option value="Selected">Selected</option>
      <option value="Rejected">Rejected</option>
    </select>
    <button id="refreshBtn">Refresh</button>
    <button id="clearBtn">Clear</button>
  </div>

  <div class="summary">
    <div class="summary-card">
      <h3 id="totalSubmissions">0</h3>
      <p>Total Submissions</p>
    </div>
    <div class="summary-card">
      <h3 id="shortlisted">0</h3>
      <p>Shortlisted</p>
    </div>
    <div class="summary-card">
      <h3 id="rejected">0</h3>
      <p>Rejected</p>
    </div>
  </div>

  <table>
    <thead>
      <tr>
        <th>Candidate</th>
        <th>Email</th>
        <th>Mobile</th>
        <th>Status</th>
        <th>Applied On</th>
        <th>Actions</th>
      </tr>
    </thead>
    <tbody id="submissionsTable">
      <tr><td colspan="6" style="text-align:center;">No submissions found.</td></tr>
    </tbody>
  </table>
</div>

<script>
(function() {
  const jobId = "${job_id}";

  async function loadSubmissions() {
    const res = await frappe.call({
      method: "qbs_ats.qbs_ats.doctype.job_creation.job_creation.get_submissions_for_job",
      args: { job_id: jobId }
    });
    renderSubmissions(res.message || []);
  }

  function renderSubmissions(data) {
    const tbody = document.getElementById("submissionsTable");
    tbody.innerHTML = "";
    if (!data.length) {
      tbody.innerHTML = "<tr><td colspan='6' style='text-align:center;'>No submissions found.</td></tr>";
      updateSummary([]);
      return;
    }
    data.forEach(row => {
      const tr = document.createElement("tr");
      tr.innerHTML = \`
        <td>\${row.candidate_name}</td>
        <td>\${row.email || ""}</td>
        <td>\${row.mobile || ""}</td>
        <td>\${row.status || ""}</td>
        <td>\${row.creation ? frappe.datetime.str_to_user(row.creation) : ""}</td>
        <td>
          <button class="btn btn-open" onclick="frappe.set_route('Form','Submission','\${row.name}')">Open</button>
          \${row.resume_url ? \`<a href="\${row.resume_url}" target="_blank" class="btn btn-resume">Resume</a>\` : ""}
        </td>
      \`;
      tbody.appendChild(tr);
    });
    updateSummary(data);
  }

  function updateSummary(data) {
    document.getElementById("totalSubmissions").innerText = data.length;
    document.getElementById("shortlisted").innerText = data.filter(d => d.status=="Selected").length;
    document.getElementById("rejected").innerText = data.filter(d => d.status=="Rejected").length;
  }

  document.getElementById("refreshBtn").addEventListener("click", loadSubmissions);
  document.getElementById("clearBtn").addEventListener("click", () => {
    document.getElementById("searchBox").value="";
    document.getElementById("statusFilter").value="";
    loadSubmissions();
  });

  loadSubmissions();
})();
</script>
    `;
}
