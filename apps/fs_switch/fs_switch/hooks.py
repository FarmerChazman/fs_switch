app_name = "fs_switch"
app_title = "FS Switch"
app_publisher = "FS Switch contributors"
app_description = "FreeSWITCH control plane for Frappe"
app_email = "maintainers@fs-switch.example"
app_license = "AGPL-3.0"

required_apps = []

after_install = "fs_switch.setup.after_install"
after_migrate = "fs_switch.tenants.after_migrate"

# Tenant membership narrows DocType role permissions to the caller's Tenants.
permission_query_conditions = {
	"FS Tenant": "fs_switch.permissions.tenant_query_conditions",
	"FS Dialplan": "fs_switch.permissions.scoped_query_conditions",
	"FS Extension": "fs_switch.permissions.scoped_query_conditions",
	"FS Gateway": "fs_switch.permissions.scoped_query_conditions",
	"FS Queue": "fs_switch.permissions.scoped_query_conditions",
}

has_permission = {
	"FS Tenant": "fs_switch.permissions.tenant_doctype_has_permission",
	"FS Dialplan": "fs_switch.permissions.tenant_has_permission",
	"FS Extension": "fs_switch.permissions.extension_has_permission",
	"FS Gateway": "fs_switch.permissions.tenant_has_permission",
	"FS Queue": "fs_switch.permissions.tenant_has_permission",
}

# The console is a standalone Vue app served from www/fs-switch.html.
# Keep the Desk untouched; FS Switch is an app page, not a Desk skin.
