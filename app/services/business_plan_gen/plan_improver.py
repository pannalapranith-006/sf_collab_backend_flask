from app.services.business_plan_gen.ai_improvements_map import IMPROVEMENT_MAP
from app.services.business_plan_gen.ai_plan_generator import generate_section
from app.extensions import db
from app.models.planSection import PlanSection


def improve_plan_from_health(plan, health):
    improvements = []

    for warning in health.get("warnings", []):
        rule = IMPROVEMENT_MAP.get(warning)
        if not rule:
            continue

        section_type = rule["section"]
        action = rule["action"]
        instruction = rule["instruction"]

        section = PlanSection.query.filter_by(
            plan_id=plan.id,
            section_type=section_type
        ).first()

        existing_content = section.content if section else ""

        new_content = generate_section(
            section_type=section_type,
            inputs={"instruction": instruction},
            existing_content=existing_content,
            action=action
        )

        if section:
            section.content = new_content
        else:
            section = PlanSection(
                plan_id=plan.id,
                section_type=section_type,
                content=new_content
            )
            db.session.add(section)

        improvements.append({
            "section": section_type,
            "reason": warning,
            "action": action
        })

    db.session.commit()
    return improvements
