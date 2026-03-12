# Atlassian Backup

This is an opinionated attempt to make backup/recovery for Confluence easier and more user friendly.  
At current stage project:
- help to back up the latest version of Confluence spaces or individual pages including all sub-pages, attachments, comments, labels, and metadata 
- help to restore backups to any Confluence space
- show preview of backup content in web browser.

Supports Confluence from Atlassian Data Center products (Confluence **Data Center** instances, not Cloud).

## Prerequisites

- Python 3.12+
- [Poetry](https://python-poetry.org/) for dependency management
- Docker (optional, for containerized execution)

## Quick Start

### 1. Configure

Copy the example environment file and fill in your values:

```bash
cp .env.example .env
```

Edit `.env`:

```env
CONFLUENCE_BASE="https://your-confluence-instance.com/"
CONFLUENCE_TOKEN="your-personal-access-token"
```

The token is a Confluence Data Center **Personal Access Token (PAT)**. Generate one from your Confluence profile under _Settings > Personal Access Tokens_.  
  
**NOTE:** The next sections (Install, Run, Browse Backup) will be executed on your local machine. Sometimes you might want to avoid installation that clutters your local machine or you would like to run this tool in more isolated manner - for this you can use execution in Docker, see [Docker](#docker) section below.

### 2. Install

```bash
make install
```

### 3. Run

```bash
# Back up an entire space
make backup URL=https://your-confluence-instance.com/display/MYSPACE

# Back up a single page and all its sub-pages
make backup URL=https://your-confluence-instance.com/pages/viewpage.action?pageId=12345

# Output as ZIP archive with custom name
make backup URL=https://your-confluence-instance.com/display/MYSPACE ARGS="--format zip --name my-backup"

# Skip raw API responses to save disk space
make backup URL=https://your-confluence-instance.com/display/MYSPACE ARGS="--no-store-raw-response"

# Verbose logging
make backup URL=https://your-confluence-instance.com/display/MYSPACE ARGS="--verbose"
```

### 4. Restore

Restore a backup to any Confluence space:

```bash
# Restore all pages, attachments, and comments to a target space
make restore DIR=output/confluence-export-202601011717-a1b2c3d4 SPACE=TARGETSPACE

# Restore under a specific parent page
make restore DIR=output/confluence-export-202601011717-a1b2c3d4 SPACE=TARGETSPACE ARGS="--parent-page-id 12345"

# Dry run -- preview what would be restored without making changes
make restore DIR=output/confluence-export-202601011717-a1b2c3d4 SPACE=TARGETSPACE ARGS="--dry-run"

# Resume an interrupted restore
make restore DIR=output/confluence-export-202601011717-a1b2c3d4 SPACE=TARGETSPACE ARGS="--resume"

# Resolve user mentions for cross-instance restores
make restore DIR=output/confluence-export-202601011717-a1b2c3d4 SPACE=TARGETSPACE ARGS="--resolve-userkeys"

# Skip attachments or comments
make restore DIR=output/confluence-export-202601011717-a1b2c3d4 SPACE=TARGETSPACE ARGS="--skip-attachments --skip-comments"

# Verbose logging
make restore DIR=output/confluence-export-202601011717-a1b2c3d4 SPACE=TARGETSPACE ARGS="--verbose"
```

The restore manifest is written next to the backup directory as `{backup-dir-name}_restore_manifest.json`. It contains the old-to-new page ID mapping and can be used to resume interrupted restores.

### 5. Browse Backup
Browse backup helps you to review or use the data from particular backup item.   
At the same time it is worth noting that a very limited amount of Confluence macros or media rendering is supported. If such case occurs - usually macros/media is displayed in grey color for indication.

```bash
make viewer DIR=output/confluence-export-202601011717-a1b2c3d4
```

Then open http://127.0.0.1:5000/ in your browser to browse pages, comments, attachments, and diagrams.

## Troubleshooting and experience from real life usage

- Mind that during backup and recovery this utility focuses on the Confluence content (info, attachment, comments..), but not on new Confluence configuration. And configuration differences between source and target Confluence instances might introduce unpredicted issues. Always rigorously review the logs in case of any issues/doubts    
- If you can't restore some big attachment files (this noticed in the logs), then you need to review the attachment size in your new Confluence configuration and set maximum size accordingly (General Configuration -> Attachment Settings -> Attachment Maximum Size)
- Due to differences in new Confluence configuration some restored attachments could not be visible. For instance, you restored draw.io diagram attachment from backup successfully, but you can't view it in Confluence - in order to fix this you need to install draw.io app for your Confluence (use admin panel for this)
- Mind that Confluence page hierarchy is unique per space, therefore if you need to perform a restoration test of the same content, then creating one more page and trying to restore under it will fail. You have to create a new space especially for this case
- As we perform backup and recovery using end user permission - it means this end user will be the new author for restored content. If you need, to have the restoration up to info about author - this requires additional development or using enterprise level tools, also it very likely that you need to make sure that "new" Confluence instance is really the similar setup from users/configs/etc prospectives. In our default restoration process scenario the author of pages will be set as user who restored them. The comments - similarly, but we also add the comment like "Originally by somebody..."
- If in source Confluence content you used Jira macros (for instance user), then after restoration you might see the "Broken link", that means such macros might be not enabled, user does not exist in new Confluence/has a different id/etc. As one approach to handle this issue for user macros we have "--resolve-userkeys" switch that adds username in plain text (it is resolved from internal id of source Confluence instance). For the other type of broken links - use your common judgment for handling such type of issues or request development services for tuning
- Obviously if some Confluence integration is not enabled or has not been properly configured you might see the other issues on the page where Jira macros are used, for instance "Unable to render.."/etc.

Newer versions of Confluence might introduce new constraints for content uniqueness, therefore sometimes during restoring on a newer Confluence version you might face recovery errors due to this constraint.


## CLI Reference

All commands run via `make` (recommended) or `poetry run`:

```
# Via make
make backup URL=<url> [ARGS="..."]
make restore DIR=<backup-dir> SPACE=<space-key> [ARGS="..."]
make viewer DIR=<backup-dir>

# Via poetry run (equivalent)
poetry run confluence-backup <url> [options]
poetry run confluence-restore <backup-dir> --space-key <KEY> [options]
poetry run confluence-backup-viewer <backup-dir> [--port PORT] [--host HOST]
```

### confluence-backup

```
confluence-backup [-h] [--name NAME] [--format {folder,zip}]
                  [--output-dir OUTPUT_DIR] [--no-store-raw-response]
                  [--env-file ENV_FILE] [--verbose] [-v] url
```

| Argument | Description |
|---|---|
| `url` | Confluence URL to back up (space or page) |
| `--name` | Custom backup name (default: auto-generated `confluence-export-{timestamp}-{id}`) |
| `--format` | Output format: `folder` (default) or `zip` |
| `--output-dir` | Parent directory for backup output (default: current directory) |
| `--no-store-raw-response` | Do not store `raw_response.json` files (saves disk space) |
| `--env-file` | Path to `.env` file (default: `.env` in current directory) |
| `--verbose` | Enable DEBUG-level logging |
| `-v, --version` | Show version |

### confluence-restore

```
confluence-restore [-h] --space-key SPACE_KEY [--parent-page-id ID]
                   [--dry-run] [--resume] [--skip-attachments]
                   [--skip-comments] [--resolve-userkeys]
                   [--env-file ENV_FILE] [--verbose] [-v] backup_dir
```

| Argument | Description |
|---|---|
| `backup_dir` | Path to backup directory (containing `backup_manifest.json`) |
| `--space-key` | Target space key to restore into (required) |
| `--parent-page-id` | Parent page ID under which to restore (default: space root) |
| `--dry-run` | Show what would be restored without making changes |
| `--resume` | Resume a previously interrupted restore |
| `--skip-attachments` | Skip attachment upload |
| `--skip-comments` | Skip comment creation |
| `--resolve-userkeys` | Replace user references with display names (for cross-instance restores) |
| `--env-file` | Path to `.env` file (default: `.env` in current directory) |
| `--verbose` | Enable DEBUG-level logging |
| `-v, --version` | Show version |

**Notes:**
- Pages are created as the authenticated user (PAT owner). Comments include an attribution line with the original author and date.
- The restore manifest (`{backup-dir}_restore_manifest.json`) is written next to the backup directory -- the backup itself is never modified.
- When using `--resume`, already-restored pages (tracked by ID mapping) are skipped. The subtree of a failed page is also skipped, since children require their parent.
- **Cross-instance restores:** Confluence user mentions (`ri:userkey`) are instance-specific. When restoring to a different instance, use `--resolve-userkeys` to replace user links with `@DisplayName` plain text. This requires `users.json` in the backup (created automatically during backup).

### Supported URL Patterns

| URL Pattern | Backup Type |
|---|---|
| `/display/{SPACEKEY}` | Full space |
| `/spaces/{SPACEKEY}` | Full space |
| `/spaces/{SPACEKEY}/overview` | Full space |
| `/display/{SPACEKEY}/{PageTitle}` | Page + sub-pages |
| `/pages/viewpage.action?pageId={id}` | Page + sub-pages |
| `/spaces/{SPACEKEY}/pages/{pageId}/{title}` | Page + sub-pages |

## Backup Output Structure

```
confluence-export-202601011717-a1b2c3d4/
├── backup_manifest.json         # Stats, page tree index, errors
├── progress.log                 # Log copy inside backup
├── users.json                   # Userkey-to-display-name mapping (for --resolve-userkeys)
├── space/
│   └── space_metadata.json      # Space name, description, homepage (space backup only)
├── pages/
│   └── {pageId}/
│       ├── page.json            # Structured: body, metadata, labels, ancestors
│       ├── raw_response.json    # Full API response (omitted with --no-store-raw-response)
│       ├── comments.json        # Comments with body.storage
│       ├── attachments.json     # Attachment metadata
│       └── attachments/         # Downloaded binary files
└── blog_posts/                  # Blog posts (space backup only)
    └── {postId}/
        ├── post.json
        ├── raw_response.json    # Full API response (omitted with --no-store-raw-response)
        └── attachments/
```

Pages are stored in flat `pages/{pageId}/` directories to avoid filesystem issues with special characters in titles. The hierarchy is preserved in `backup_manifest.json`.

Each page is stored twice: `page.json` (structured, typed data) and `raw_response.json` (verbatim API response for future recovery).  
  
Why both?  
- page.json is what the tool actually uses for restore, viewing, and processing — it's compact and typed
- raw_response.json is the safety precaution: if we ever need data we didn't extract (e.g., userKey fields for the user collector feature we just built, or some future field), it's all there without needing to re-query the API. It's the "full API response for future recovery".  
  
By the way if you make sure your backup contains all necessary info and recovery meets your expectation (for instance, you performed manual recovery check or make test-e2e plus manual validation), then for the sake of disk space saving you could use --no-store-raw-response switch during backup, so raw_response.json will not be stored in final backup output.


## Error Handling

The backup is designed to be resilient -- individual item failures do not abort the entire backup.

| Error | Behavior |
|---|---|
| Missing config / bad `.env` | Fatal -- abort with message |
| Auth failure (401) | Fatal -- abort, suggest checking PAT |
| Page 403 / 404 | Non-fatal -- skip, log warning, record in manifest |
| Attachment download failure | Non-fatal -- skip, log, continue |
| Network error after retries | Non-fatal per item, logged |
| Disk write failure | Fatal -- abort |

HTTP requests are retried automatically with exponential backoff on 429 (rate limit), 500, 502, 503, and 504 responses.

All errors are recorded in `backup_manifest.json` under the `errors` array.

### Restore

The restore process follows the same resilient pattern:

| Error | Behavior |
|---|---|
| Missing config / bad `.env` | Fatal -- abort with message |
| Auth failure (401) | Fatal -- abort |
| Target space not accessible | Fatal -- abort |
| Page creation failure | Non-fatal -- skip page and its subtree, log, record in manifest |
| Attachment upload failure | Non-fatal -- skip, log, continue |
| Comment creation failure | Non-fatal -- skip, log, continue |
| Label addition failure | Non-fatal -- skip, log, continue |

All errors are recorded in the restore manifest under the `errors` array.

## Known Limitations

- **Attachments are fully buffered in memory** during both backup (download) and restore (upload). For spaces with very large attachments (100 MB+), this may cause high memory usage. Use `--skip-attachments` if memory is a concern, or process such spaces on a machine with sufficient RAM.
- **`--resume` skips already-restored pages entirely.** If a page was created successfully but its attachments or comments failed partway through an interrupted restore, resuming will not retry those failed items. Workaround: delete the page from the target space, remove its entry from the restore manifest JSON, and resume again.

## Docker

### Build

```bash
make docker-build
```

**Note:** The Dockerfile contains a commented-out step for installing a Cloudflare WARP CA certificate. If your organization uses Cloudflare WARP for network access, uncomment that block in the Dockerfile before building.

### Run

```bash
# Back up an entire space
make docker-backup URL=https://your-confluence-instance.com/display/MYSPACE

# Back up with custom name and verbose logging
make docker-backup URL=https://your-confluence-instance.com/spaces/ME/pages/12345/My+Page ARGS="--name my-backup --verbose"

# Output as ZIP archive
make docker-backup URL=https://your-confluence-instance.com/display/MYSPACE ARGS="--format zip"

# Skip raw API responses to save disk space
make docker-backup URL=https://your-confluence-instance.com/display/MYSPACE ARGS="--no-store-raw-response"
```

This mounts `./output` and `./logs` as volumes and passes the `.env` file for configuration. The `ARGS` variable passes additional options (same as the local `make backup` command).

### Restore in Docker

```bash
# Restore backup to a space
make docker-restore DIR=output/confluence-export-202601011717-a1b2c3d4 SPACE=TARGETSPACE

# Dry run
make docker-restore DIR=output/confluence-export-202601011717-a1b2c3d4 SPACE=TARGETSPACE ARGS="--dry-run --verbose"
```

### Browse Backup in Docker

```bash
make docker-viewer DIR=output/confluence-export-202601011717-a1b2c3d4

# Custom port
make docker-viewer DIR=output/confluence-export-202601011717-a1b2c3d4 PORT=8080
```

Mounts the backup directory as a read-only volume and starts the viewer on the specified port (default 5000). Open http://127.0.0.1:5000/ in your browser.

### Validate in Docker

```bash
make docker-validate
```

Builds the image and runs lint, type checks, and tests inside the container.

## Development

Python is used for application development, poetry for dependencies and execution, also many commands/tests are wrapped in Makefile, so you can use them as pure make targets.  

Make sure that you have real Confluence instance from Atlassian Data Center.
For instance, you can use this project for creation of local development Confluence instance: https://github.com/oshablovskyy/confluence-dc-docker

It is suggested use run validate/test/test-integration/test-e2e after adding new features.  
For test-e2e sure that you reviewed/update scripts tests/integration accordingly to your config settings and generated ".envBackupSource" and ".envRecoveryTarget".

### Running Validation

```bash
make validate
```

This runs all checks in sequence: formatting, linting, type checking, and unit tests.

### Make Targets

| Target | Description |
|---|---|
| `make help` | Show all available targets |
| `make install` | Install dependencies with Poetry into local `.venv` |
| `make backup` | Run Confluence backup (`URL=` required, optional `ARGS=`) |
| `make restore` | Restore from backup (`DIR=` and `SPACE=` required, optional `ARGS=`) |
| `make viewer` | Start backup viewer (`DIR=` required) |
| `make test` | Run unit tests |
| `make test-integration` | Run integration tests against real Confluence |
| `make test-e2e` | Run end-to-end backup/restore cycle against real Confluence |
| `make lint` | Run ruff linter |
| `make typecheck` | Run mypy type checker (strict mode) |
| `make format` | Run ruff formatter + auto-fix |
| `make validate` | Run format + lint + typecheck + tests |
| `make docker-build` | Build Docker image |
| `make docker-backup` | Run backup in Docker (`URL=` required, optional `ARGS=`) |
| `make docker-restore` | Run restore in Docker (`DIR=` and `SPACE=` required, optional `ARGS=`) |
| `make docker-viewer` | Start backup viewer in Docker (`DIR=` required, optional `PORT=`) |
| `make docker-validate` | Run validation in Docker |
| `make clean` | Remove build artifacts and caches |


### Project Layout

```
src/atlassian_backup/
├── shared/                   # Reusable across Jira, Confluence, etc.
│   ├── auth.py               # BearerTokenAuth (PAT)
│   ├── config.py             # .env loading via python-dotenv
│   ├── http_client.py        # requests.Session + urllib3 Retry
│   ├── logging_setup.py      # Dual logging: /logs + backup dir
│   ├── pagination.py         # Generic offset-based paginated fetcher (generator)
│   ├── backup_writer.py      # Write JSON/binary to folder, optional ZIP
│   └── url_parser.py         # Base URL parsing utilities
└── confluence/
    ├── cli.py                # Backup CLI entry point
    ├── restore_cli.py        # Restore CLI entry point
    ├── client.py             # Confluence REST API client (read + write)
    ├── models.py             # Dataclasses: Page, Space, BlogPost, BackupManifest, RestoreManifest
    ├── url_parser.py         # Detect space vs page from URL patterns
    ├── backup_orchestrator.py # Backup coordinator
    ├── restore_orchestrator.py # Restore coordinator
    ├── page_exporter.py      # Recursive page tree export
    ├── page_restorer.py      # Page, label, attachment, comment restore
    ├── attachment_exporter.py # Download attachments
    ├── comment_exporter.py   # Comment export
    ├── blog_exporter.py      # Blog post export (space-level)
    ├── blog_restorer.py      # Blog post restore
    ├── space_exporter.py     # Space metadata export
    ├── user_collector.py     # Collect userkey-to-displayName mapping during backup
    ├── user_resolver.py      # Resolve user references during restore
    └── viewer/               # Read-only web viewer (Flask)
        ├── cli.py            # Viewer CLI entry point
        ├── app.py            # Flask app factory + routes
        ├── backup_reader.py  # Read backup data from disk
        ├── content_renderer.py # Confluence storage HTML -> browser HTML
        ├── templates/        # Jinja2 templates
        └── static/           # CSS styles
```

The `shared/` package is designed for reuse when adding Jira or other Atlassian product backups.

### Dependencies

**Runtime:** `requests`, `python-dotenv`, `flask`

**Dev:** `pytest`, `pytest-cov`, `responses`, `ruff`, `mypy`, `types-requests`

### Support and Development
If you are interested in support and development of this project - feel free to contact me.
