# Plugins

[Català](./README.md) · [Español](./README.es.md) · [English](./README.en.md)

Client plugins are checked out here while working locally. This folder is not a Django app, and its contents, other than these READMEs, do not enter the public repository or the GitHub image.

The loader, the routes, and the server image are documented in [backend/docs/plugins.md](../backend/docs/plugins.md). This file is the convention for what a plugin looks like.

A feature that not every installation has belongs in a plugin. What ships with the product (Giswater, Odoo, smart metering) stays in the `integrations` app. A small change to a function or a template still uses `*_personalized.py`.

## Repository

Each plugin is its own repository. It is cloned here:

```text
plugins/<nom>/
  Dockerfile
  <nom>/
    __init__.py
    apps.py
    signals.py
    tasks.py
    migrations/
```

`<nom>` is a Python identifier (`^[A-Za-z_][A-Za-z0-9_]*$`). The inner directory has the same name as the parent repository. The imported module is `<nom>`: the loader adds `plugins/<nom>/` to `sys.path`, not the package directory.

<!-- coderabbit-ai-generated:v1 -->

<!-- coderabbit-ai-generated-section:v1:d81b455691477d69587bcf1d17250728760d54963f40dd118ad0adbcee226b39 -->

With the default Compose configuration, adding `PLUGINS` to `.env` does not make the local checkout accessible inside containers. Create `docker-compose.override.yml` at the repository root to mount `./plugins` at `/plugins` in the Django services (the GMAO consumer only runs with its profile):

```yaml
services:
  backend:
    volumes:
      - ./plugins:/plugins:ro
  celery-worker:
    volumes:
      - ./plugins:/plugins:ro
  celery-beat:
    volumes:
      - ./plugins:/plugins:ro
  gmao-consumer:
    volumes:
      - ./plugins:/plugins:ro
```

With the layout above, set `PLUGINS=<nom>` in `.env` (comma-separated for multiple names). The loader will find `/plugins/<nom>/<nom>/`. This override loads automatically with the default Compose configuration; if you set `COMPOSE_FILE`, include it explicitly in that list. Alternatively, build the private image in the “Image” section, which makes the package importable inside the container.

<!-- /coderabbit-ai-generated:v1 -->

The core does not import the plugin. `AppConfig.ready()` registers the signals.

## Activation

`PLUGINS` in `.env` is the comma-separated list. Without the variable, no plugin is loaded. If a name cannot be imported, the process does not start.

<!-- coderabbit-ai-generated:v1 -->

<!-- coderabbit-ai-generated-section:v1:fb20dfe704b1ad3392a8199c23dfe1061aea3355d4182eb982ba7f7f4ac7567c -->

`PLUGINS` is read at process startup and is not written into the image. After changing or removing it from `.env`, recreate the affected services with `docker compose up -d --force-recreate backend celery-worker celery-beat` (add `gmao-consumer` if the GMAO profile is active). Restarting containers is not sufficient: existing containers retain the environment they were created with.

<!-- /coderabbit-ai-generated:v1 -->

## Practices

- A signal that fails is logged and does not block the product's `save()`.
- A Celery task is enqueued inside `transaction.on_commit`. The worker, beat, and the GMAO consumer must use the same image as the backend, because otherwise the task does not exist.
- `QuerySet.update()` does not fire signals. A change the plugin must observe goes through the model's `save()`.
- Secrets are read from the environment, inside the plugin. They are not added to `customers/settings.py`.
- Configuration that differs per installation goes in `ConfigProject`, seeded by a plugin migration with an empty value. Empty means the plugin does nothing.
- Migrations belong to the plugin app and run only where `PLUGINS` includes it. The dependency on the product is declared explicitly.
<!-- coderabbit-ai-generated:v1 -->

<!-- coderabbit-ai-generated-section:v1:aebd23ad031be02b1f435b69ec43e6a768e47af8ce30131ae1cbe6bc895f30d9 -->

- With `API_URL_PREFIX=True`, a `urls.py` is published at `/api/<nom>/`; if the product already uses the name prefix, it is published at `/api/plugins/<nom>/`. With `API_URL_PREFIX` disabled, the addresses are `/<nom>/` and `/plugins/<nom>/`, respectively. Without routes, there is no `urls.py`.

<!-- /coderabbit-ai-generated:v1 -->
- The name must not match an already imported module or a package in the image.
- The public repository does not name any specific plugin. The name, the URL, and the secrets live in the plugin repository.

## Image

The public image does not contain plugins. The plugin is published separately, as a thin image based on a release that already contains the loader:

<!-- coderabbit-ai-generated:v1 -->

<!-- coderabbit-ai-generated-section:v1:20d0ad0d724a38c62154c9494e967e54d7e41f08c3c74f5e9535dd1638aaf993 -->

```dockerfile
ARG CUSTOMERS_VERSION
FROM ghcr.io/aqua360/aqua360-customers-backend:${CUSTOMERS_VERSION}

COPY exemple /opt/plugins/exemple
ENV PYTHONPATH=/opt/plugins
```

<!-- /coderabbit-ai-generated:v1 -->

<!-- coderabbit-ai-generated:v1 -->

<!-- coderabbit-ai-generated-section:v1:b344fee3635c16e0f17b092c4c8b4f4f54f6992766fb93b4e11d1261199e99f9 -->

The `FROM` is always the product's public image. A plugin is never the base of another: when there are several, they are all copied onto that public image.

The server keeps running `ghcr.io/aqua360/aqua360-customers-backend:${CUSTOMERS_VERSION}`. That choice applies to the backend, the worker, beat, the GMAO consumer, and the frontend. No variable replaces this image. `BACKEND_IMAGE` and `docker-compose.image.yml` are not how a plugin is deployed.

The `.env` lists the plugins and each one's registry, without a tag. The tag is `CUSTOMERS_VERSION`. Inside a `.env` value that reference is not expanded.

```dotenv
CUSTOMERS_VERSION=<versió>
PLUGINS=exemple,altre
PLUGIN_IMAGE_exemple=ghcr.io/exemple/plugin-exemple
PLUGIN_IMAGE_altre=ghcr.io/exemple/plugin-altre
```

`PLUGINS` is what Django reads. `PLUGIN_IMAGE_<nom>` is what the step that, before start, copies `/opt/plugins/<nom>` from each image onto the public one uses. If that code is not in the image that starts, the process does not start. A plugin that only reacts to signals does not add screens: the frontend is already compiled.

<!-- coderabbit-ai-generated:v1 -->

<!-- coderabbit-ai-generated-section:v1:f7a1f6109fb6cfb4bbf858eede4823004fac420b17643ba3ecec980d91bfc2a5 -->

The plugin’s GHCR package is private. Each server must use a separate classic personal access token with the `read:packages` scope, an expiration date, and rotation planned before expiry. The associated account must have access only to the required packages. Run `docker login ghcr.io` on each server as the system user that runs `docker compose pull`. Servers that only use the public image need no credentials.

<!-- /coderabbit-ai-generated:v1 -->

A deploy key opens `git clone` of the plugin repository. It does not authorize `docker pull` of the package.

<!-- coderabbit-ai-generated:v1 -->

<!-- coderabbit-ai-generated-section:v1:b27b81a9933ff8db1b1a0bfab8b5737f6a77cd1a69c6af8ba9d9186c141c7ce3 -->

Tokens are not committed. Store them securely and revoke old tokens after rotation.

<!-- /coderabbit-ai-generated:v1 -->
