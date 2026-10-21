app_name = "fs_switch"
app_title = "FS Switch"
app_publisher = "FS Switch contributors"
app_description = "FreeSWITCH control plane for Frappe"
app_email = "maintainers@fs-switch.example"
app_license = "AGPL-3.0"

required_apps = []

after_install = "fs_switch.setup.after_install"

# The console is a standalone Vue app served from www/fs-switch.html.
# Keep the Desk untouched; FS Switch is an app page, not a Desk skin.
