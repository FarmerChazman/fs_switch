# Contributing

FS Switch is an AGPL-3.0 project. By contributing you agree that your changes
are licensed under the same terms.

The public repository is
<https://github.com/FarmerChazman/fs_switch>.

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
   npm ci
   npm run build
   ```

   Use `npm run dev` for the Vite dev server.

5. Run the checks:

   ```bash
   python -m compileall apps/fs_switch tests
   python -m unittest discover -s tests -v
   git diff --check
   ```

   `pytest tests` works too if you have pytest installed.

## Style

- Python: tabs, Frappe conventions, no secrets in code.
- Vue: Composition API, `<script setup>`, PrimeVue components.
- Keep client-specific branding out of the repository. Use the neutral
  `fs_switch` mark in `apps/fs_switch/fs_switch/public/images`.
- Never commit `.env`, SIP credentials, ESL passwords or production hostnames.
- Keep XML as compiler output. Do not add a second source of truth for routing.

## Documentation and changelog

Every user-visible change updates at least one of:

- [`README.md`](README.md) for installation, configuration or the feature
  overview,
- [`docs/ui.md`](docs/ui.md) for console behaviour,
- [`docs/flow-model.md`](docs/flow-model.md) for the Flow graph, compiler,
  simulator, publish lifecycle or diff,
- [`docs/architecture.md`](docs/architecture.md) for boundaries, cache or live
  events,
- [`CHANGELOG.md`](CHANGELOG.md) for the release summary.

Architectural changes add an ADR under [`docs/adr/`](docs/adr). Deferred work
belongs in [`docs/DEFERRED.md`](docs/DEFERRED.md).

## Pull requests

Describe the change, the FreeSWITCH version tested against, and whether the
change affects the XML-curl contract. Include a test or a manual verification
note. Keep changes focused.

CI runs the Python unit tests and the frontend build. A pull request should pass
both before merge. Do not include generated console assets unless the change
intentionally updates the shipped bundle.

## Security

Do not report vulnerabilities in a public issue. Follow
[`SECURITY.md`](SECURITY.md).
