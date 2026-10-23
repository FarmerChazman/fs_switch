"""Create the app roles and reconcile Tenant membership projections."""

from fs_switch.tenants import ensure_default_tenant, ensure_tenant_roles, sync_all_user_roles


def execute():
	ensure_default_tenant()
	ensure_tenant_roles()
	sync_all_user_roles()
