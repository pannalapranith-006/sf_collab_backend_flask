def generate_match_explanation(builder_profile, vision):
    reasons = []

    if builder_profile.skills:
        reasons.append("Relevant skills for required roles")

    if vision.sector in (builder_profile.industries_interested or []):
        reasons.append(f"Interested in {vision.sector}")

    if (builder_profile.completed_projects or 0) > 5:
        reasons.append("Strong project experience")

    if (builder_profile.rating or 0) > 4:
        reasons.append("Highly rated builder")

    return reasons