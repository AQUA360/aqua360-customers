# opscripts

One-off maintenance/data scripts, run automatically on deploy — independent from Django
migrations, for things like data backfills or admin fixes that shouldn't be launched by hand.

To add a script to any app:
1. Create an `opscripts/` package next to that app's `models.py` (with `__init__.py`), if
   it doesn't exist yet.
2. Add a numbered module, e.g. `0001_backfill_something.py`, exposing a `run()` function.

`python manage.py run_pending_scripts` (wired into `docker-entrypoint.sh` right after
`migrate`) executes every app's opscripts in filename order, once per environment, and
records completion in `coredata.ExecutedScript`. A script only ever runs once per
environment — it does not need to be idempotent itself, but should fail loudly (raise) if
something is wrong, since a failure aborts the deploy's `run_pending_scripts` step.
