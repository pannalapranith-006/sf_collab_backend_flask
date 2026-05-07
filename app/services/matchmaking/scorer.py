def calculate_match_score(builder_profile, vision):
    score = 0

    # -------------------------
    # 1. Skill Overlap (40%)
    # -------------------------
    skill_score = calculate_skill_overlap(builder_profile.skill_tags, vision.roles_needed)
    score += skill_score * 0.4

    # -------------------------
    # 2. Sector Alignment (30%)
    # -------------------------
    sector_score = 1 if vision.sector in (builder_profile.sector_interests or []) else 0
    score += sector_score * 0.3

    # -------------------------
    # 3. Execution Score (20%)
    # -------------------------
    execution_score = (builder_profile.execution_score or 0) / 100
    score += execution_score * 0.2

    # -------------------------
    # 4. Availability (10%)
    # -------------------------
    availability_score = 1 if builder_profile.availability == "AVAILABLE" else 0
    score += availability_score * 0.1

    return round(score * 100, 2)


# ----------------------------------------
# Helper: Skill Matching Logic
# ----------------------------------------
def calculate_skill_overlap(builder_skills, roles_needed):
    if not builder_skills or not roles_needed:
        return 0

    builder_skills_set = set([s.lower() for s in builder_skills])

    role_skill_map = {
        "ml engineer": ["machine learning", "python"],
        "backend engineer": ["backend", "apis", "python", "java"],
        "frontend engineer": ["react", "javascript", "frontend"],
        "data scientist": ["machine learning", "data analysis", "python"],
    }

    required_skills = set()

    for role in roles_needed:
        mapped = role_skill_map.get(role.lower(), [])
        required_skills.update([s.lower() for s in mapped])

    if not required_skills:
        return 0

    overlap = builder_skills_set.intersection(required_skills)

    return len(overlap) / len(required_skills)