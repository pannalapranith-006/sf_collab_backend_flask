from app.models.builder import BuilderProfile  # existing one
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

        score = calculate_match_score(builder, vision)
        explanation = generate_match_explanation(builder, vision)

        results.append({
            "builder_id": builder.user_id,
            "score": score,
            "profile": builder.to_dict(),
            "explanation": explanation
        })

    results.sort(key=lambda x: x["score"], reverse=True)

    return results[:limit]