# Contributing

FS Switch is an AGPL-3.0 project. By contributing you agree that your changes
are licensed under the same terms.

## Development setup

1. Create a Frappe v16 bench.
2. Copy or symlink this repository into `apps/fs_switch`.
3. Install the app on a development site:

   ```bash
   bench --site dev.localhost install-app fs_switch
   bench --site dev.localhost migrate
   ```

4. Build the console:

   ```bash
   cd apps/fs_switch/frontend
   yarn install
   yarn build
   ```

5. Run the small checks:

   ```bash
   python -m compileall apps/fs_switch
   python -m json.tool apps/fs_switch/fs_switch/hooks.py >/dev/null 2>&1 || true
   cd tests && python -m pytest
   ```

## Style

- Python: tabs, Frappe conventions, no secrets in code.
- Vue: Composition API, `<script setup>`, PrimeVue components.
- Keep client-specific branding out of the repository. Use the neutral
  `fs_switch` mark in `apps/fs_switch/fs_switch/public/images`.
- Never commit `.env`, SIP credentials, ESL passwords or production hostnames.

## Pull requests

Describe the change, the FreeSWITCH version tested against, and whether the
change affects the XML-curl contract. Include a test or a manual verification
note. Keep changes focused.
