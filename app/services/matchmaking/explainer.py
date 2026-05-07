def generate_match_explanation(builder_profile, vision):
    reasons = []

    # Skill match
    if builder_profile.skill_tags and vision.roles_needed:
        reasons.append("Strong skill alignment with required roles")

    # Sector match
    if vision.sector in (builder_profile.sector_interests or []):
        reasons.append(f"Interested in {vision.sector}")

    # Execution
    if (builder_profile.execution_score or 0) > 70:
        reasons.append("High execution track record")

    # Availability
    if builder_profile.availability == "AVAILABLE":
        reasons.append("Currently available to collaborate")

    return reasons