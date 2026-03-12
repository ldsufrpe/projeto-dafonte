from typing import Any

def unwrap_datasnap(payload: dict[str, Any]) -> list[Any]:
    """
    Unwraps the DataSnap nested response format.
    DataSnap usually returns: {"result": [[[ {data1}, {data2} ]]] }
    This function attempts to extract the innermost list of dictionaries.
    """
    if not isinstance(payload, dict):
        return []
        
    result = payload.get("result")
    if not result:
        return []
        
    # DataSnap wraps the actual data in multiple lists.
    # We unwrap until we find either a list of dicts, or just return what we have.
    current = result
    while isinstance(current, list) and len(current) > 0 and isinstance(current[0], list):
        current = current[0]
        
    return current
