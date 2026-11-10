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

The core does not import the plugin. `AppConfig.ready()` registers the signals.

## Activation

`PLUGINS` in `.env` is the comma-separated list. Without the variable, no plugin is loaded. If a name cannot be imported, the process does not start.

`PLUGINS` is read when the container starts. It is not written into the image: removing it from `.env` leaves the process without that plugin.

## Practices

- A signal that fails is logged and does not block the product's `save()`.
- A Celery task is enqueued inside `transaction.on_commit`. The worker, beat, and the GMAO consumer must use the same image as the backend, because otherwise the task does not exist.
- `QuerySet.update()` does not fire signals. A change the plugin must observe goes through the model's `save()`.
- Secrets are read from the environment, inside the plugin. They are not added to `customers/settings.py`.
- Configuration that differs per installation goes in `ConfigProject`, seeded by a plugin migration with an empty value. Empty means the plugin does nothing.
- Migrations belong to the plugin app and run only where `PLUGINS` includes it. The dependency on the product is declared explicitly.
- A `urls.py` is published at `/<nom>/`. If the product already uses that prefix, it is published at `/plugins/<nom>/`. Without routes, there is no `urls.py`.
- The name must not match an already imported module or a package in the image.
- The public repository does not name any specific plugin. The name, the URL, and the secrets live in the plugin repository.

## Image

The public image does not contain plugins. The plugin is published separately, as a thin image based on a release that already contains the loader:

```dockerfile
ARG CUSTOMERS_VERSION=local
FROM ghcr.io/aqua360/aqua360-customers-backend:${CUSTOMERS_VERSION}

COPY exemple /opt/plugins/exemple
ENV PYTHONPATH=/opt/plugins
```

When a new product release is published, this image is rebuilt with the `FROM` of that tag. In the client's `.env`:

```dotenv
COMPOSE_FILE=docker-compose.yml:docker-compose.image.yml
BACKEND_IMAGE=ghcr.io/exemple/backend-amb-plugin:v<versió>
PLUGINS=exemple
```

`docker-compose.image.yml` sets `BACKEND_IMAGE` on the backend, the worker, beat, and the GMAO consumer, and removes their `build`. The frontend stays on the public image: a plugin that only reacts to signals does not add screens, because the frontend is already compiled.

The plugin's GHCR package is private. One classic personal access token is enough to pull it, with the `read:packages` scope and no expiration. The same `docker login` is repeated on every server that must pull this image, as the system user that runs `docker compose pull`. There is no GitHub user per machine. Servers that only use the public image need no credential.

A deploy key opens `git clone` of the plugin repository. It does not authorize `docker pull` of the package.

The token is not committed. GitHub deletes tokens that go unused for a year; a `docker pull` from any server keeps it alive.
