"""Helpers del cicle d'estat d'un SendBatch (tokens a ConfigProject: 0/1/2)."""


def payload_is_final_batch_result(payload) -> bool:
    """
    True si el JSON d'estat del lot és tractable com a resultat final
    (pot contenir errors d'ítems; el que importa és que el puguem desar).
    """
    if not isinstance(payload, dict) or not payload.get("batch_id"):
        return False
    if "results" in payload:
        return True
    if payload.get("finished_at"):
        return True
    if isinstance(payload.get("summary"), dict):
        return True
    provider_status = str(payload.get("status") or "").strip().lower()
    return provider_status in {
        "done",
        "completed",
        "finished",
        "error",
        "failed",
        "finalized",
    }
