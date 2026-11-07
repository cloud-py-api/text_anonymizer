<!--
SPDX-FileCopyrightText: 2026 Nextcloud GmbH and Nextcloud contributors
SPDX-License-Identifier: AGPL-3.0-or-later
-->

# Nextcloud Text Anonymizer

A Nextcloud ExApp that redacts personal and sensitive information from text and text files.
Useful when using the text in, for example, AI prompts where there may be a risk of such text being leaked.

Uses [Presidio](https://presidio.dataprivacystack.org/) under the hood.

## Development

For building and running the ExApp for development:

```bash
# Activate the virtual environment
$(poetry env activate)

# Install dependencies
poetry install

# Start the app server (example)
APP_HOST=0.0.0.0 APP_ID=text_anonymizer APP_PORT=9040 APP_SECRET=12345 APP_VERSION=0.1.0 NEXTCLOUD_URL=http://nextcloud.local COMPUTE_DEVICE=CPU python3 ex_app/lib/main.py

# Register and enable the app in a local nextcloud-docker-dev environment
make register
```

### License

[AGPL-3.0-or-later](./LICENSES/AGPL-3.0-or-later.txt)
