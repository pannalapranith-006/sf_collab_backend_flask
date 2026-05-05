from flask import Blueprint, request
from flask_jwt_extended import jwt_required, get_jwt_identity
from app.extensions import db
from app.models.businessPlan import BusinessPlan
from app.models.planSection import PlanSection
from app.models.planFinancial import PlanFinancial
from app.utils.helper import success_response, error_response
from datetime import datetime
from app.services.business_plan_gen.financial_calculator import calculate_financials
from app.services.pdf_exporter import export_business_plan_pdf
from app.services.business_plan_gen.ai_plan_generator import generate_section
from app.services.docx_exporter import export_business_plan_docx
from app.services.business_plan_gen.financial_analyzer import analyze_financials
from app.services.business_plan_gen.plan_versioning import create_plan_version
from app.services.business_plan_gen.ai_advisor import generate_advisor_response
from app.services.business_plan_gen.financial_scenario import generate_financial_scenarios
from app.services.business_plan_gen.plan_health import evaluate_plan_health
from app.services.business_plan_gen.plan_improver import improve_plan_from_health
from app.models.planVersion import PlanVersion


import os

plans_bp = Blueprint('plans', __name__, url_prefix='/api/plans')

@plans_bp.route('', methods=['POST'])
@jwt_required()
def create_plan():
    try:
        user_id = get_jwt_identity()
        data = request.get_json()

        title = data.get('title')
        industry = data.get('industry')
        stage = data.get('stage')

        if not title:
            return error_response('Title is required', 400)

        plan = BusinessPlan(
            user_id=user_id,
            title=title,
            industry=industry,
            stage=stage
        )

        db.session.add(plan)
        db.session.commit()

        return success_response({
            'plan': plan.to_dict()
        }, 'Plan created', 201)

    except Exception as e:
        db.session.rollback()
        return error_response(str(e), 500)

@plans_bp.route('/<int:plan_id>', methods=['GET'])
@jwt_required()
def get_plan(plan_id):
    try:
        user_id = get_jwt_identity()

        plan = BusinessPlan.query.filter_by(
            id=plan_id,
            user_id=user_id
        ).first()

        if not plan:
            return error_response('Plan not found', 404)

        sections = PlanSection.query.filter_by(plan_id=plan.id).all()
        financials = PlanFinancial.query.filter_by(plan_id=plan.id).first()

        return success_response({
            'plan': plan.to_dict(),
            'sections': [s.to_dict() for s in sections],
            'financials': financials.to_dict() if financials else None
        })

    except Exception as e:
        return error_response(str(e), 500)

@plans_bp.route('/<int:plan_id>/financials', methods=['PUT'])
@jwt_required()
def save_financials(plan_id):
    user_id = get_jwt_identity()
    data = request.get_json()

    plan = BusinessPlan.query.filter_by(id=plan_id, user_id=user_id).first()
    if not plan:
        return error_response("Plan not found", 404)

    financials = PlanFinancial.query.filter_by(plan_id=plan_id).first()

    if not financials:
        financials = PlanFinancial(
            plan_id=plan_id,
            revenue_inputs=data.get("revenue_inputs", {}),
            expense_inputs=data.get("expense_inputs", {}),
            assumptions=data.get("assumptions", {})
        )
        db.session.add(financials)
    else:
        financials.revenue_inputs = data.get("revenue_inputs", financials.revenue_inputs)
        financials.expense_inputs = data.get("expense_inputs", financials.expense_inputs)
        financials.assumptions = data.get("assumptions", financials.assumptions)

    db.session.commit()

    return success_response(financials.to_dict(), "Financials saved")

@plans_bp.route('/<int:plan_id>/financials', methods=['GET'])
@jwt_required()
def get_financials(plan_id):
    user_id = get_jwt_identity()

    plan = BusinessPlan.query.filter_by(id=plan_id, user_id=user_id).first()
    if not plan:
        return error_response("Plan not found", 404)

    financials = PlanFinancial.query.filter_by(plan_id=plan_id).first()
    if not financials:
        return success_response({
            "projections": [],
            "break_even_year": None
        })

    years = financials.assumptions.get("projection_years", 3)

    result = calculate_financials(
        financials.revenue_inputs,
        financials.expense_inputs,
        years
    )

    return success_response(result)

@plans_bp.route('/<int:plan_id>/export', methods=['POST'])
@jwt_required()
def export_plan(plan_id):
    user_id = get_jwt_identity()

    plan = BusinessPlan.query.filter_by(id=plan_id, user_id=user_id).first()
    if not plan:
        return error_response("Plan not found", 404)

    sections = PlanSection.query.filter_by(plan_id=plan.id).all()
    financials = PlanFinancial.query.filter_by(plan_id=plan.id).first()

    file_path = export_business_plan_pdf(plan, sections, financials)

    return success_response({
        "file": os.path.basename(file_path),
        "path": file_path
    }, "PDF generated successfully")
    
    
@plans_bp.route('/<int:plan_id>/ai', methods=['POST'])
@jwt_required()
def generate_ai_section(plan_id):
    user_id = get_jwt_identity()
    data = request.get_json()

    section_type = data.get("section_type")
    inputs = data.get("inputs", {})
    action = data.get("action", "generate")

    plan = BusinessPlan.query.filter_by(id=plan_id, user_id=user_id).first()
    if not plan:
        return error_response("Plan not found", 404)

    section = PlanSection.query.filter_by(
        plan_id=plan.id,
        section_type=section_type
    ).first()

    existing_content = section.content if section else None

    try:
        content = generate_section(
            section_type=section_type,
            inputs=inputs,
            existing_content=existing_content,
            action=action
        )
    except Exception as e:
        return error_response(str(e), 500)

    if not section:
        section = PlanSection(
            plan_id=plan.id,
            section_type=section_type,
            content=content
        )
        db.session.add(section)
    else:
        section.content = content

    db.session.commit()

    return success_response({
        "section": section.to_dict()
    }, "Section generated")
    
@plans_bp.route('/<int:plan_id>/export/docx', methods=['POST'])
@jwt_required()
def export_plan_docx(plan_id):
    user_id = get_jwt_identity()

    plan = BusinessPlan.query.filter_by(id=plan_id, user_id=user_id).first()
    if not plan:
        return error_response("Plan not found", 404)

    sections = PlanSection.query.filter_by(plan_id=plan.id).all()
    financials = PlanFinancial.query.filter_by(plan_id=plan.id).first()

    projections = []
    if financials:
        result = calculate_financials(
            financials.revenue_inputs,
            financials.expense_inputs,
            financials.assumptions.get("projection_years", 3)
        )
        projections = result["projections"]

    file_path = export_business_plan_docx(
        plan,
        sections,
        financials,
        projections
    )

    return success_response({
        "file": os.path.basename(file_path),
        "path": file_path
    }, "DOCX generated successfully")


@plans_bp.route('/<int:plan_id>/ai/generate-all', methods=['POST'])
@jwt_required()
def generate_all_sections(plan_id):
    user_id = get_jwt_identity()
    data = request.get_json() or {}

    inputs = data.get("inputs", {})

    plan = BusinessPlan.query.filter_by(id=plan_id, user_id=user_id).first()
    if not plan:
        return error_response("Plan not found", 404)

    SECTION_ORDER = [
        "executive_summary",
        "problem_solution",
        "market_overview",
        "business_model",
        "operations",
        "marketing",
        "financial_narrative"
    ]

    generated_sections = []

    try:
        for section_type in SECTION_ORDER:
            section = PlanSection.query.filter_by(
                plan_id=plan.id,
                section_type=section_type
            ).first()

            existing_content = section.content if section else None

            content = generate_section(
                section_type=section_type,
                inputs=inputs,
                existing_content=existing_content,
                action="generate"
            )

            if not section:
                section = PlanSection(
                    plan_id=plan.id,
                    section_type=section_type,
                    content=content
                )
                db.session.add(section)
            else:
                section.content = content
            db.session.flush()
            generated_sections.append(section.to_dict())

        db.session.commit()

        return success_response(
            {
                "sections": generated_sections
            },
            "All sections generated successfully"
        )

    except Exception as e:
        db.session.rollback()
        return error_response(str(e), 500)
    

@plans_bp.route('/<int:plan_id>/financials/analyze', methods=['POST'])
@jwt_required()
def analyze_plan_financials(plan_id):
    user_id = get_jwt_identity()
    data = request.get_json()

    scenario = data.get("scenario", "base")

    plan = BusinessPlan.query.filter_by(id=plan_id, user_id=user_id).first()
    if not plan:
        return error_response("Plan not found", 404)

    financials = PlanFinancial.query.filter_by(plan_id=plan.id).first()
    if not financials:
        return error_response("Financial data missing", 400)

    analysis = analyze_financials(
        plan,
        financials.revenue_inputs,
        financials.expense_inputs,
        scenario
    )

    create_plan_version(
        plan_id=plan.id,
        trigger_type="financial_analysis",
        summary=f"Financial analysis updated ({scenario})"
    )

    return success_response(analysis, "Financial analysis completed")



@plans_bp.route('/<int:plan_id>/advisor', methods=['POST'])
@jwt_required()
def plan_ai_advisor(plan_id):
    user_id = get_jwt_identity()

    plan = BusinessPlan.query.filter_by(id=plan_id, user_id=user_id).first()
    if not plan:
        return error_response("Plan not found", 404)

    financials = PlanFinancial.query.filter_by(plan_id=plan.id).first()
    if not financials:
        return error_response("Financials not found", 400)

    analysis = analyze_financials(
        plan,
        financials.revenue_inputs,
        financials.expense_inputs,
        scenario="base"
    )

    advisor_response = generate_advisor_response(plan, analysis)

    return success_response({
        "advisor_feedback": advisor_response,
        "analysis": analysis
    }, "AI advisor feedback generated")

@plans_bp.route('/<int:plan_id>/financials/scenarios', methods=['GET'])
@jwt_required()
def get_financial_scenarios(plan_id):
    user_id = get_jwt_identity()

    plan = BusinessPlan.query.filter_by(id=plan_id, user_id=user_id).first()
    if not plan or not plan.financials:
        return error_response("Financial data not found", 404)

    scenarios = generate_financial_scenarios(plan.financials)

    return success_response({
        "scenarios": scenarios
    }, "Scenario analysis generated")
    
    
@plans_bp.route('/<int:plan_id>/health', methods=['GET'])
@jwt_required()
def get_plan_health(plan_id):
    user_id = get_jwt_identity()

    plan = BusinessPlan.query.filter_by(id=plan_id, user_id=user_id).first()
    if not plan or not plan.financials:
        return error_response("Plan or financials not found", 404)

    scenarios = generate_financial_scenarios(plan.financials)
    health = evaluate_plan_health(plan,scenarios)

    return success_response({
        "health": health,
        "scenarios": scenarios
    }, "Plan health evaluated")


@plans_bp.route('/<int:plan_id>/improve', methods=['POST'])
@jwt_required()
def improve_plan(plan_id):
    user_id = get_jwt_identity()

    plan = BusinessPlan.query.filter_by(id=plan_id, user_id=user_id).first()
    if not plan or not plan.financials:
        return error_response("Plan or financials not found", 404)

    scenarios = generate_financial_scenarios(plan.financials)
    health = evaluate_plan_health(plan, scenarios)

    improvements = improve_plan_from_health(plan, health)
    create_plan_version(
    plan_id=plan.id,
    trigger_type="ai_improvement",
    summary=f"AI improvement suggestions generated (score {health['score']})",
    health_score=health["score"],
    health_status=health["grade"]
    )

    return success_response({
        "health_before": health,
        "improvements_applied": improvements
    }, "Plan improved using AI")


@plans_bp.route("/<int:plan_id>/versions", methods=["GET"])
@jwt_required()
def list_plan_versions(plan_id):
    user_id = get_jwt_identity()

    plan = BusinessPlan.query.filter_by(id=plan_id, user_id=user_id).first()
    if not plan:
        return error_response("Plan not found", 404)

    versions = (
        PlanVersion.query
        .filter_by(plan_id=plan_id)
        .order_by(PlanVersion.version_number.desc())
        .all()
    )

    return success_response([v.to_dict() for v in versions])


@plans_bp.route("/<int:plan_id>/versions/<int:version>", methods=["GET"])
@jwt_required()
def get_plan_version(plan_id, version):
    v = PlanVersion.query.filter_by(
        plan_id=plan_id,
        version_number=version
    ).first()

    if not v:
        return error_response("Version not found", 404)

    return success_response(v.to_dict())
