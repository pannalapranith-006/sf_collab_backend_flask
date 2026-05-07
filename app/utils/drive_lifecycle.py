ALLOWED_TRANSITIONS = {
    "uploaded": ["active"],
    "active": ["archived", "deleted"],
    "archived": ["active", "deleted"],
    "deleted": []
}


def validate_transition(current_state, new_state):
    if current_state == new_state:
        return True

    allowed = ALLOWED_TRANSITIONS.get(current_state, [])
    return new_state in allowed