from integrations.outbound.giswater.tasks import (
    fetch_giswater_connecs_task,
    sync_giswater_connections_task,
    sync_giswater_suply_cuts_task
)
from integrations.outbound.signing.tasks import poll_signing_sessions_task

__all__ = [
    "fetch_giswater_connecs_task", 
    "sync_giswater_connections_task", 
    "sync_giswater_suply_cuts_task",
    "poll_signing_sessions_task",
]
