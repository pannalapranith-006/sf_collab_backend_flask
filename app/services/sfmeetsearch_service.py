from app.models.sfmeetsearch_models import Transcript, Summary, Decision, Meeting


def search_data(query, workspace_id):

    if not query:
        return {"error": "query required"}, 400

    try:
        query = query.strip()

        meetings = Meeting.query.filter(
            Meeting.workspace_id == workspace_id,
            Meeting.title.ilike(f"%{query}%")
        ).limit(10).all()

        transcripts = Transcript.query.filter(
            Transcript.workspace_id == workspace_id,
            Transcript.content.ilike(f"%{query}%")
        ).limit(10).all()

        summaries = Summary.query.filter(
            Summary.workspace_id == workspace_id,
            Summary.content.ilike(f"%{query}%")
        ).limit(10).all()

        decisions = Decision.query.filter(
            Decision.workspace_id == workspace_id,
            Decision.content.ilike(f"%{query}%")
        ).limit(10).all()

        return {
            "results": {
                "meetings": [
                    {"id": m.id, "title": m.title, "type": "meeting"}
                    for m in meetings
                ],
                "transcripts": [
                    {"id": t.id, "content": (t.content or "")[:100], "type": "transcript"}
                    for t in transcripts
                ],
                "summaries": [
                    {"id": s.id, "content": (s.content or "")[:100], "type": "summary"}
                    for s in summaries
                ],
                "decisions": [
                    {"id": d.id, "content": (d.content or "")[:100], "type": "decision"}
                    for d in decisions
                ]
            }
        }, 200

    except Exception as e:
        return {"error": str(e)}, 500