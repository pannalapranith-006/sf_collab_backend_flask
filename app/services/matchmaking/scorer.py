def calculate_match_score(builder_profile, vision):
    score = 0

    # -------------------------
    # 1. Skill Overlap (40%)
    # -------------------------
    builder_skills = [s.name.lower() for s in builder_profile.skills]
    skill_score = calculate_skill_overlap(builder_skills, vision.roles_needed)
    score += skill_score * 0.4

    # -------------------------
    # 2. Sector Alignment (30%)
    # -------------------------
    sector_score = 1 if vision.sector in (builder_profile.industries_interested or []) else 0
    score += sector_score * 0.3

    # -------------------------
    # 3. Execution Score (20%)
    # -------------------------
    execution_score = calculate_execution_score(builder_profile)
    score += execution_score * 0.2

    # -------------------------
    # 4. Availability (10%)
    # -------------------------
    # Not present → assume available for MVP
    availability_score = 1
    score += availability_score * 0.1

    return round(score * 100, 2)


# ----------------------------------------
# Execution Score Logic
# ----------------------------------------
def calculate_execution_score(builder_profile):
    projects = builder_profile.completed_projects or 0
    rating = builder_profile.rating or 0

    # Normalize
    project_score = min(projects / 10, 1)   # cap at 10 projects
    rating_score = rating / 5              # rating out of 5

    return (project_score + rating_score) / 2


# ----------------------------------------
# Skill Matching
# ----------------------------------------
def calculate_skill_overlap(builder_skills, roles_needed):
    if not builder_skills or not roles_needed:
        return 0

    builder_skills_set = set(builder_skills)

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