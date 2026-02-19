frappe.provide('prompt_crm_navbar');

// 🎨 Color Constants (from your theme.txt)
const PRIMARY_BLUE = '#329BBB';
const PRIMARY_BLUE_DARK = '#183b72';
const TEXT_DARK = '#4c5a67';
const TEXT_LIGHT = '#fff';
const HOVER_LIGHT = '#dfe6ff';
const ACTIVE_UNDERLINE = '#214695';

// 👇 Inline SVG Icons (matches Frappe’s icon style)
function getIconSVG(name) {
    const icons = {
        'dashboard': `<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="3" width="7" height="9" rx="1"/><rect x="14" y="3" width="7" height="5" rx="1"/><rect x="14" y="12" width="7" height="9" rx="1"/></svg>`,
        'user-plus': `<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M16 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"/><circle cx="8.5" cy="7" r="4"/><line x1="20" y1="8" x2="20" y2="14"/><line x1="17" y1="11" x2="23" y2="11"/></svg>`,
        'briefcase': `<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="2" y="7" width="20" height="14" rx="2" ry="2"/><path d="M16 21V5a2 2 0 0 0-2-2H6a2 2 0 0 0-2 2v16"/></svg>`,
        'building': `<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="2" width="16" height="20" rx="2" ry="2"/><line x1="11" y1="10" x2="11" y2="14"/><line x1="7" y1="10" x2="7" y2="14"/><line x1="15" y1="10" x2="15" y2="14"/><line x1="7" y1="18" x2="17" y2="18"/></svg>`,
        'address-card': `<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="2" y="2" width="20" height="20" rx="2" ry="2"/><circle cx="12" cy="10" r="3"/><path d="M7 20.662V19a2 2 0 0 1 2-2h6a2 2 0 0 1 2 2v1.662"/></svg>`,
        'file-alt': `<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/><line x1="16" y1="13" x2="8" y2="13"/><line x1="16" y1="17" x2="8" y2="17"/><line x1="10" y1="9" x2="8" y2="9"/></svg>`
    };
    return icons[name] || `<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/></svg>`;
}

prompt_crm_navbar.initNavbar = function () {
    // 🚫 Cleanup (idempotent)
    $('.prompt-crm-nav-bar').remove();

    const route = frappe.get_route();
    if (['login', 'setup', 'app'].includes(route[0]) && route[1] === 'home') return;

    try {
        const $navbar = $('.navbar');
        if ($navbar.length === 0) {
            setTimeout(prompt_crm_navbar.initNavbar, 300);
            return;
        }

        // ✅ CRM Nav Bar — Styled to match your theme
        const $bar = $(`
            <div class="prompt-crm-nav-bar flex align-center justify-content-center" style="
                display: flex;
                align-items: center;
                gap: 48px;
                padding: 0 24px;
                height: 100%;
                background: ${PRIMARY_BLUE};
                color: ${TEXT_LIGHT};
                font-size: 15px;
                font-weight: 500;
                white-space: nowrap;
                overflow-x: auto;
                -webkit-overflow-scrolling: touch;
                width: 100vw;
            "></div>
        `);

        const items = [


            { label: "Client", route: ["List", "Client"], icon: "dashboard" },

            { label: "Job Opening", route: ["List", "Job Opening"], icon: "user-plus" },
            { label: "Job Applicant", route: ["List", "Job Applicant"], icon: "briefcase" },
            { label: "Interview", route: ["List", "Interview"], icon: "building" },
            { label: "Job Offer", route: ["List", "Job Offer"], icon: "address-card" },
            { label: "Dashboard", route: ["Dashboard-view", "ATS"], icon: "file-alt" },
            { label: "Report", route: ["List", "Report"], icon: "file-alt" },
            { label: "Insights", route: ["List", "Insights"], icon: "file-alt" }


        ];

        items.forEach(item => {
            const isActive = (
                (item.label === 'Dashboard' && (route[0] === 'dashboard' || (route[0] === 'dashboard' && route[1]))) ||
                (Array.isArray(item.route) && route[0] === item.route[0] && route[1] === item.route[1])
            );  

            const $link = $(`
                <a href="#" class="crm-nav-link ${isActive ? 'active' : ''}" style="
                    display: inline-flex;
                    align-items: center;
                    gap: 6px;
                    padding: 8px 0;
                    color: ${TEXT_LIGHT};
                    text-decoration: none;
                    position: relative;
                    transition: color 0.2s;
                ">
                    <span class="crm-icon" style="
                        display: inline-block;
                        width: 16px;
                    ">${getIconSVG(item.icon)}</span>
                    <span>${item.label}</span>
                    ${isActive ? `<span style="
                        position: absolute;
                        bottom: 0;
                        left: 0;
                        right: 0;
                        height: 5px;
                        background: ${ACTIVE_UNDERLINE};
                        border-radius: 18px;
                    "></span>` : ''}
                </a>
            `).on('click', function (e) {
                e.preventDefault();
                frappe.set_route(...(Array.isArray(item.route) ? item.route : [item.route]));
            }).on('mouseenter', function () {
                $(this).css('color', HOVER_LIGHT);
            }).on('mouseleave', function () {
                $(this).css('color', TEXT_LIGHT);
            });

            $bar.append($link);
        });

        // 🔌 Inject into navbar — after search, before user menu
        const $search = $navbar.find('.awesome-bar');
        const $user = $navbar.find('.navbar-user-menu');

        if ($search.length) {
            $bar.insertAfter($search);
        } else if ($user.length) {
            $bar.insertBefore($user);
        } else {
            $navbar.append($bar);
        }

        // 🔁 Auto-highlight active route (improved)
        const updateActive = () => {
            const r = frappe.get_route();
            $bar.find('.crm-nav-link').each(function () {
                const $el = $(this);
                const label = $el.find('span:last').text().trim(); // Trim whitespace

                let active = false;

                // Handle Dashboard
                if (r[0] === 'dashboard') {
                    // Also accept if route is ['dashboard', 'Some Dashboard Name']
                    if (label === 'Dashboard') {
                        active = true;
                    }
                }
                // Handle List pages
                else if (r[0] === 'List' && r[1]) {
                    const target = r[1];
                    const matchLabels = {
                        'Lead': 'Leads',
                        'Opportunity': 'Opportunity',
                        'Customer': 'Customers',
                        'Contact': 'Contacts',
                        'Report': 'Reports'
                    };
                    if (matchLabels[target] && label === matchLabels[target]) {
                        active = true;
                    }
                }

                $el.toggleClass('active', active)
                    .css('color', active ? HOVER_LIGHT : TEXT_LIGHT);

                // Update underline
                if (active && !$el.find('.active-underline').length) {
                    $el.append(`<span class="active-underline" style="
                position: absolute;
                bottom: 0;
                left: 0;
                right: 0;
                height: 5px;
                background: ${ACTIVE_UNDERLINE};
                border-radius: 18px;
            "></span>`);
                } else if (!active) {
                    $el.find('.active-underline').remove();
                }
            });
        };

        setTimeout(updateActive, 100);
        frappe.router.on('change', updateActive);

    } catch (e) {
        console.warn('CRM Nav Bar initNavbar failed', e);
        setTimeout(prompt_crm_navbar.initNavbar, 500);
    }
};
// ===== FOOTER INIT =====
prompt_crm_navbar.initFooter = function () {
    $('.prompt-crm-footer').remove(); // idempotent

    const route = frappe.get_route();
    if (['login', 'setup', 'app'].includes(route[0]) && route[1] === 'home') return;

    // Insert footer at end of <body>
    const $footer = $(`
        <div class="prompt-crm-footer" style="
            position: fixed;
            bottom: 0;
            left: 0;
            width: 100%;
            background: #214695;
            color: ${TEXT_LIGHT};
            text-align: center;
            padding: 8px 0;
            font-size: 13px;
            z-index: 1000;
            box-shadow: 0 -2px 6px rgba(0,0,0,0.08);
        ">
            A Solution by <strong>Q10 Analytics Private Limited</strong>
        </div>
    `).appendTo('body');

    // Adjust main content to avoid overlap
    const footerHeight = $footer.outerHeight();
    $('.layout-main-section, .desk-body, .standard-page').css({
        'padding-bottom': `${footerHeight + 8}px`,
        'transition': 'padding-bottom 0.3s'
    });

    // Cleanup on SPA page change
    $(document).one('page-change', function () {
        $('.prompt-crm-footer').remove();
        $('.layout-main-section, .desk-body, .standard-page').css('padding-bottom', '');
    });
};
// ===== INIT (safe, SPA-aware) =====
function safeInit() {
    const route = frappe.get_route();
    // Ensure Poppins font is loaded
    if (!document.getElementById('poppins-font')) {
        const link = document.createElement('link');
        link.id = 'poppins-font';
        link.rel = 'stylesheet';
        link.href = 'https://fonts.googleapis.com/css2?family=Poppins:wght@300;400;500;600;700&display=swap';
        document.head.appendChild(link);
    }
    // if (['login', 'app'].includes(route[0]) && route[1] === 'home') {
    //     $('.prompt-crm-nav-bar, .prompt-crm-footer').remove();
    //     $('.layout-main-section, .desk-body, .standard-page').css('padding-bottom', '');
    //     return;
    // }
    try {
        prompt_crm_navbar.initNavbar();
        prompt_crm_navbar.initFooter();
    } catch (e) {
        setTimeout(safeInit, 300);
    }
}

$(document).ready(safeInit);
frappe.router.on('change', safeInit);
$(document).on('desk-ready app-ready page-change', safeInit);