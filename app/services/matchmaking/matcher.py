from app.models.builder_profile import BuilderProfile
from app.models.vision import Vision
from app.services.matchmaking.scorer import calculate_match_score
from app.services.matchmaking.explainer import generate_match_explanation


def find_matches_for_vision(vision_id, limit=10):
    vision = Vision.query.get(vision_id)

    if not vision:
        return []

    builders = BuilderProfile.query.all()

    results = []

    for builder in builders:

        # Skip creator
        if builder.user_id == vision.creator_id:
            continue

        # Filter availability
        if builder.availability not in ["AVAILABLE", "OPEN"]:
            continue

        score = calculate_match_score(builder, vision)

        explanation = generate_match_explanation(builder, vision)

        results.append({
            "builder_id": builder.user_id,
            "score": score,
            "profile": builder.to_dict(),
            "explanation": explanation
        })

    # Sort by score DESC
    results.sort(key=lambda x: x["score"], reverse=True)

    return results[:limit]