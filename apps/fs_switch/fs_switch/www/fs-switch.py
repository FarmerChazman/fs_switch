import frappe


def get_context(context):
	if frappe.session.user == "Guest":
		frappe.local.flags.redirect_location = "/login?redirect-to=/fs-switch"
		raise frappe.Redirect

	context.no_cache = 1
	context.csrf_token = frappe.sessions.get_csrf_token()
	context.site_name = frappe.local.site
	context.fs_switch_user = {
		"name": frappe.session.user,
		"full_name": frappe.utils.get_fullname(frappe.session.user),
		"is_admin": "System Manager" in frappe.get_roles(),
	}
	return context
