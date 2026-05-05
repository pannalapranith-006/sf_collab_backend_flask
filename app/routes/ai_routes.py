import os
import uuid
import json
import re
from flask import Blueprint, request, jsonify, current_app
from flask_jwt_extended import jwt_required, get_jwt_identity
from openai import OpenAI
import base64
from app.models.user import User
from app.extensions import db
from flask import Blueprint, request, jsonify, send_file
from dotenv import load_dotenv
from groq import Groq
from werkzeug.utils import secure_filename
from pathlib import Path
import logging
from datetime import datetime
import requests
# from flask_jwt_extended import jwt_required, get_jwt_identity
from app.models.user import User
from app.services.ai_assistant.ingest import ingest_document
from app.services.ai_assistant.rag import ask_assistant
from app.services.ai_image_gen import generate_image
from app.services.ai_core.ai_service import AIService
from app.services.ai_core.response_builder import build_refusal

# Load environment variables
load_dotenv()

# Create blueprint
ai_bp = Blueprint('qwen', __name__)

# Configuration


BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '../..'))
QWN_UPLOAD_FOLDER = os.path.join(BASE_DIR, 'uploads', 'qwen_generated')  # Changed name

# Create upload folder
Path(QWN_UPLOAD_FOLDER).mkdir(parents=True, exist_ok=True)

# Available models
AVAILABLE_MODELS = [
    # "openai/gpt-oss-20b",
    "qwen/qwen3-32b"
]

def standard_response(success=True, data=None, error=None, code=200):
    response = jsonify({
        'success': success,
        'data': data,
        'error': error
    })
    return response, code

# ============================================================
# QWEN ROUTES
# ============================================================
def total_credits(user):
    wallet_credits = user.wallet.credits if user.wallet else 0
    return wallet_credits + (user.credits or 0)
#! HEALTH CHECK
@ai_bp.route('/health', methods=['GET'])
def qwen_health():
    """Health check endpoint"""
    OPENAI_API_KEY = current_app.config.get("OPENAI_API_KEY")
    GROQ_API_KEY = current_app.config.get("GROQ_API_KEY")
    try:
        status = {
            'status': 'ready' if GROQ_API_KEY or OPENAI_API_KEY else 'no_api_key',
            'openai_api_key': bool(OPENAI_API_KEY),
            'groq_api_key': bool(GROQ_API_KEY),
            'version': '1.0.0',
            'models_available': len(AVAILABLE_MODELS),
            'timestamp': datetime.now().isoformat()
        }
        return standard_response(True, status)
    except Exception as e:
        logging.error(f'Health check error: {str(e)}')
        return standard_response(False, None, str(e), 500)

#! GET AVAILABLE MODELS
@ai_bp.route('/models', methods=['GET'])
def get_models():
    """Get available models"""
    try:
        # Add model details
        model_details = {
            'openai/gpt-oss-20b': {
                'name': 'GPT-OSS-20B',
                'description': 'OpenAI 20B parameter model for general tasks',
                'max_tokens': 2048
            },
            'qwen/qwen3-32b': {
                'name': 'Qwen 3 32B',
                'description': 'Advanced Qwen model with 32B parameters',
                'max_tokens': 4096
            }
        }
        return standard_response(True, {
            'models': AVAILABLE_MODELS,
            'model_details': model_details
        })
    except Exception as e:
        logging.error(f'Error getting models: {str(e)}')
        return standard_response(False, None, str(e), 500)

# GENERATE CONTENT
#     """Generate content (chat, business plan, pitch deck) with structured JSON output"""
#     try:
#         if request.method == 'OPTIONS':
#             return standard_response(True, {}, code=200)
#         data = request.get_json()

#         if not data or 'prompt' not in data:
#             return standard_response(False, None, 'Missing prompt in request', 400)
#         OPENAI_API_KEY = current_app.config.get("OPENAI_API_KEY")
#         GROQ_API_KEY = current_app.config.get("GROQ_API_KEY")
#         groq_client = get_groq_client()

#         prompt = data.get('prompt')
#         model = data.get('model', AVAILABLE_MODELS[0])
#         content_type = data.get('content_type', 'chat')  # chat, business_plan, pitch_deck
#         temperature = data.get('temperature', 0.7)
#         max_tokens = data.get('max_tokens', 2048)
#         output_format = data.get('output_format', 'text')  # text, json
        
#         if model not in AVAILABLE_MODELS:
#             return standard_response(False, None, f'Model not available. Choose from: {AVAILABLE_MODELS}', 400)
        
#         client = None
#         if model == 'qwen/qwen3-32b':
#             client = get_groq_client()
#         elif model == 'openai/gpt-oss-20b':
#             client = get_openai_client()

#         if not client:
#             return standard_response(False, None, 'API key not configured for selected model', 500)
#         # Simplified system prompts
#         system_prompts = {
#             'chat': '''You are a helpful and professional AI assistant. Provide accurate, detailed, and well-structured responses in Markdown format.''',
            
#             'business_plan': '''You are an expert business consultant specializing in startup development. 
#             Generate a comprehensive, professional business plan in Markdown format.
            
#             Include these sections:
#             1. Executive Summary
#             2. Company Description
#             3. Market Analysis
#             4. Products & Services
#             5. Marketing Strategy
#             6. Operations Plan
#             7. Management Team
#             8. Financial Projections
#             9. Funding Needs
#             10. Risk Analysis
            
#             Use proper Markdown formatting with headers, lists, tables where appropriate.
#             Include realistic numbers and data.''',
            
#             'pitch_deck': '''You are a pitch deck expert and venture capital advisor. 
#             Generate compelling, investor-ready pitch deck content in Markdown format.
            
#             Structure it as a pitch deck with these slides:
#             1. Title Slide
#             2. The Problem
#             3. The Solution
#             4. Market Opportunity
#             5. Product
#             6. Business Model
#             7. Traction
#             8. Competition
#             9. Team
#             10. Financials
#             11. Funding Ask
#             12. Contact
            
#             Use proper Markdown formatting. Make it visually descriptive and include quantifiable metrics.'''
#         }
        
#         system_prompt = system_prompts.get(content_type, system_prompts['chat'])
        
#         # Enhance prompt based on content type
#         if content_type == 'business_plan':
#             enhanced_prompt = f"""Create a comprehensive, investor-ready business plan for: {prompt}
            
#             Please include:
#             1. Specific, quantifiable data where applicable
#             2. Realistic financial projections
#             3. Detailed market analysis
#             4. Clear operational plans
#             5. Risk assessment and mitigation strategies
            
#             Format the response in Markdown with clear sections and proper formatting."""
            
#         elif content_type == 'pitch_deck':
#             enhanced_prompt = f"""Create a compelling, investor-focused pitch deck for: {prompt}
            
#             Requirements:
#             1. Make it visually descriptive (imagine each slide's content)
#             2. Include quantifiable metrics and projections
#             3. Highlight competitive advantages clearly
#             4. Focus on traction and proof points
#             5. Structure for a 10-12 minute presentation
            
#             Format the response in Markdown with slide titles and bullet points."""
            
#         else:
#             enhanced_prompt = prompt
#         response_text = ""
#         if model == 'qwen/qwen3-32b' and content_type in ['business_plan', 'pitch_deck']:
#             max_tokens = min(max_tokens, 4096)

#             # Call Groq API - REMOVE response_format for now to avoid JSON validation issues
#             chat_completion = groq_client.chat.completions.create(
#                 messages=[
#                     {"role": "system", "content": system_prompt},
#                     {"role": "user", "content": enhanced_prompt}
#                 ],
#                 model=model,
#                 temperature=temperature,
#                 max_tokens=max_tokens,
#                 response_format={"type": "json_object"} if content_type in ['business_plan', 'pitch_deck'] else None
#             )
#             response_text = chat_completion.choices[0].message.content
        
#         elif model == 'openai/gpt-oss-20b':
#             # Call OpenAI API directly
#             headers = {
#                 'Authorization': f'Bearer {OPENAI_API_KEY}',
#                 'Content-Type': 'application/json'
#             }

#             payload = {
#                 "model": "gpt-4.1-mini",
#                 "messages": [
#                     {
#                         "role": "system",
#                         "content": [
#                             {"type": "text", "text": system_prompt}
#                         ]
#                     },
#                     {
#                         "role": "user",
#                         "content": [
#                             {"type": "text", "text": enhanced_prompt}
#                         ]
#                     }
#                 ],
#                 "temperature": temperature,
#                 "max_tokens": max_tokens
#             }
            
#             response = client.responses.create(
#                 model="gpt-4.1-mini",
#                 input=enhanced_prompt,
#                 temperature=temperature,
#                 max_output_tokens=max_tokens
#             )
#             test_responses = extract_text_from_response(response, expect_json=True, strict=True)


#             chat_completion = response.json()
        
        
#         # Generate downloadable content
#         download_formats = ['txt', 'md']
#         download_links = {}
        
#         timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        
#         for fmt in download_formats:
#             filename = f"{content_type}_{timestamp}.{fmt}"
#             filepath = os.path.join(QWN_UPLOAD_FOLDER, filename)
            
#             try:
#                 with open(filepath, 'w', encoding='utf-8') as f:
#                     if fmt == 'md':
#                         f.write(f"# {content_type.replace('_', ' ').title()}\n\n")
#                         f.write(f"**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
#                         f.write(f"**Model:** {model}\n")
#                         f.write(f"**Prompt:** {prompt[:200]}...\n\n")
#                         f.write("---\n\n")
#                         f.write(response_text)
#                     else:  # txt
#                         f.write(response_text)
                
#                 download_links[fmt] = f"/api/qwen/download/{filename}"
                
#             except Exception as e:
#                 logging.error(f"Error creating {fmt} file: {str(e)}")
        
#         return standard_response(True, {
#             'response': response_text,  # Return as text, not parsed JSON
#             'model': model,
#             'content_type': content_type,
#             'download_links': download_links,
#             'timestamp': datetime.now().isoformat(),
#             'tokens_used': chat_completion.usage.total_tokens if hasattr(chat_completion, 'usage') else None,
#             'format': 'markdown'
#         })
    
#     except Exception as e:
#         logging.error(f'Generation error: {str(e)}')
@ai_bp.route('/generate', methods=['POST', 'OPTIONS'])
def qwen_generate():
    """Generate content (chat, business plan, pitch deck) in Markdown"""
    try:
        if request.method == 'OPTIONS':
            return standard_response(True, {}, code=200)

        data = request.get_json()
        if not data or 'prompt' not in data:
            return standard_response(False, None, 'Missing prompt in request', 400)

        prompt = data.get('prompt')

        if isinstance(prompt, list):
            prompt = "\n".join(map(str, prompt))
        elif not isinstance(prompt, str):
            prompt = str(prompt)

        model = data.get('model', AVAILABLE_MODELS[0])
        content_type = data.get('content_type', 'chat')
        temperature = data.get('temperature', 0.7)
        max_tokens = data.get('max_tokens', 2048)
        if model not in AVAILABLE_MODELS:
            return standard_response(
                False, None, f'Model not available. Choose from: {AVAILABLE_MODELS}', 400
            )

        # =========================
        # SYSTEM PROMPTS
        # =========================
        system_prompts = {
            'chat': (
                "You are a helpful and professional AI assistant. "
                "Provide accurate, detailed, well-structured responses in Markdown."
            ),
            'pitch_deck': (
                "You are a venture capital pitch expert.\n\n"
                "Generate investor-ready pitch deck content in Markdown.\n\n"
                "Slides:\n"
                "1. Title\n2. Problem\n3. Solution\n4. Market\n5. Product\n"
                "6. Business Model\n7. Traction\n8. Competition\n9. Team\n"
                "10. Financials\n11. Funding Ask\n12. Contact"
            ),
        }

        system_prompt = system_prompts.get(content_type, system_prompts['chat'])

        # =========================
        # PROMPT ENHANCEMENT
        # =========================
        if content_type == 'business_plan':
            enhanced_prompt = (
                "Create an investor-ready business plan for:\n\n"
                f"{prompt}\n\n"
                "Include realistic financials, market sizing, risks, and operations."
            )

        elif content_type == 'pitch_deck':
            enhanced_prompt = (
                "Create an investor-focused pitch deck for:\n\n"
                f"{prompt}\n\n"
                "Include metrics, traction, competitive advantages, and projections."
            )
        else:
            enhanced_prompt = prompt

        response_text, tokens_used = get_response(model, system_prompt, enhanced_prompt, temperature=temperature, max_tokens=max_tokens)

        # =========================
        # FILE GENERATION
        # =========================
        download_links = {}
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')

        for fmt in ['txt', 'md']:
            filename = f"{content_type}_{timestamp}.{fmt}"
            filepath = os.path.join(QWN_UPLOAD_FOLDER, filename)

            try:
                with open(filepath, 'w', encoding='utf-8') as f:
                    if fmt == 'md':
                        f.write(f"# {content_type.replace('_', ' ').title()}\n\n")
                        f.write(f"**Generated:** {datetime.utcnow().isoformat()} UTC\n")
                        f.write(f"**Model:** {model}\n\n---\n\n")
                    f.write(response_text)

                download_links[fmt] = f"/api/ai/download/{filename}"

            except Exception as e:
                logging.error(f"File generation failed: {e}")

        # =========================
        # RESPONSE
        # =========================
        return standard_response(True, {
            "response": response_text,
            "model": model,
            "content_type": content_type,
            "download_links": download_links,
            "timestamp": datetime.utcnow().isoformat(),
            "tokens_used": tokens_used,
            "format": "markdown",
        })

    except Exception as e:
        logging.exception("Generation error")
        return standard_response(False, None, str(e), 500)


def format_metadata_block(metadata: dict) -> str:
            if not metadata:
                return ""

            lines = []
            for key, value in metadata.items():
                if value:
                    label = key.replace("_", " ").title()
                    lines.append(f"- **{label}:** {value}")

            if not lines:
                return ""

            return (
                "### Context & Constraints (User-Provided Metadata)\n"
                + "\n".join(lines)
                + "\n\n"
            )

@ai_bp.route('/business-ideas', methods=['POST', 'OPTIONS'])
@jwt_required()
def qwen_business_ideas():
    try:
        if request.method == 'OPTIONS':
            return standard_response(True, {}, code=200)

        data = request.get_json() or {}
        content_type = data.get('content_type', 'business_ideas')
        if content_type not in ['business_ideas', 'business_plan']:
            return standard_response(False, None, 'Invalid content_type. Choose business_ideas or business_plan', 400)

        user_id = get_jwt_identity()
        user = User.query.get(user_id)
        if not user:
            return standard_response(False, None, 'User not found', 404)

        # Temporary fallback to keep service bootable when prompt template is unavailable.
        return standard_response(
            True,
            {
                'message': 'business-ideas endpoint is temporarily in fallback mode',
                'content_type': content_type
            },
            code=200
        )
    except Exception as e:
        logging.exception("Qwen business ideas error")
        return standard_response(False, None, str(e), 500)

### Chat 
@ai_bp.route('/chat', methods=['POST', 'OPTIONS'])
def qwen_chat():
    """
    Chat-style endpoint compatible with frontend QwenChat.jsx
    """
    try:
        if request.method == 'OPTIONS':
            return standard_response(True, {}, code=200)

        data = request.get_json()

        if not data or 'messages' not in data:
            return standard_response(False, None, 'Missing messages in request', 400)

        messages = data.get('messages', [])
        temperature = data.get('temperature', 0.7)
        max_tokens = data.get('max_tokens', 2048)

        # Convert conversation → prompt
        prompt_lines = []

        for msg in messages:
            role = msg.get('role', 'user')
            content = msg.get('content', '')

            if content:
                prompt_lines.append(f"{role.capitalize()}: {content}")

        final_prompt = "\n".join(prompt_lines)

        # Use AIService (HF Proxy + Guardrails)
        result = AIService.generate(
            feature="chat",
            user_input=final_prompt,
            temperature=temperature,
            max_tokens=max_tokens
        )
        
        return standard_response(True,result)
        # return standard_response(True, AIService.remove_thinking(result))

    except Exception as e:
        logging.exception("Qwen chat error")
        return standard_response(False, None, str(e), 500)

        
# Helper methods to add to your class
def _json_to_markdown(self, data, level=1):
    """Convert JSON structure to Markdown"""
    markdown = ""
    if isinstance(data, dict):
        for key, value in data.items():
            header = "#" * level
            if isinstance(value, (dict, list)):
                markdown += f"{header} {key.replace('_', ' ').title()}\n\n"
                markdown += self._json_to_markdown(value, level + 1)
            else:
                markdown += f"**{key.replace('_', ' ').title()}:** {value}\n\n"
    elif isinstance(data, list):
        for item in data:
            if isinstance(item, (dict, list)):
                markdown += self._json_to_markdown(item, level)
            else:
                markdown += f"- {item}\n"
        markdown += "\n"
    else:
        markdown += f"{data}\n\n"
    return markdown

def _json_to_text(self, data, indent=0):
    """Convert JSON structure to readable text"""
    text = ""
    indent_str = "  " * indent
    
    if isinstance(data, dict):
        for key, value in data.items():
            text += f"{indent_str}{key.replace('_', ' ').title()}:\n"
            text += self._json_to_text(value, indent + 1)
    elif isinstance(data, list):
        for i, item in enumerate(data, 1):
            text += f"{indent_str}{i}. "
            if isinstance(item, (dict, list)):
                text += "\n" + self._json_to_text(item, indent + 1)
            else:
                text += f"{item}\n"
    else:
        text += f"{indent_str}{data}\n"
    
    return text
    
    
#! DOWNLOAD GENERATED CONTENT
@ai_bp.route('/download/<filename>', methods=['GET'])
def download_content(filename):
    """Download generated content"""
    try:
        filepath = os.path.join(QWN_UPLOAD_FOLDER, secure_filename(filename))  # Use QWN_UPLOAD_FOLDER
        
        if not os.path.exists(filepath):
            return standard_response(False, None, 'File not found', 404)
        
        return send_file(
            filepath,
            as_attachment=True,
            download_name=filename,
            mimetype='text/plain'
        )
    
    except Exception as e:
        logging.error(f'Download error: {str(e)}')
        return standard_response(False, None, str(e), 500)



@ai_bp.route("/logo/generate", methods=["POST", "OPTIONS"])
@jwt_required()
def generate_logo():
    if request.method == 'OPTIONS':
        return standard_response(True, {}, code=200)

    user_id = get_jwt_identity()
    user = User.query.get(user_id)

    if not user:
        return jsonify({"error": "Unauthorized"}), 401

    data = request.get_json()

    brand_name = data.get("brandName")
    industry = data.get("industry", "technology")
    style = data.get("style", "minimal")
    colors = data.get("colors", [])
    additional_notes = data.get("additionalNotes", "")
    subtitle = data.get("subtitle", "")
    symbol = data.get("symbol", "abstract")

    if not brand_name:
        return jsonify({"error": "brandName is required"}), 400

    COST_PER_IMAGE = 50
    IMAGE_COUNT = data.get("imagesAmount", 2)

    total_cost = COST_PER_IMAGE * IMAGE_COUNT

    if not total_credits(user) < total_cost:
        return jsonify({"error": "Not enough credits"}), 402

    # =========================
    # 🔹 AI SLOGAN GENERATION (SECURE)
    # =========================

    slogan_prompt = f"""
You are a professional brand designer.

Return ONLY valid JSON.
Do not include markdown.
Do not include explanations.
Do not include comments.

Schema:
[
{{
    "font_family": "string",
    "font_weight": number,
    "letter_spacing": number,
    "text_case": "uppercase | title | sentence",
    "alignment": "center | left",
    "placement": "below | right | stacked",
    "mood": "string"
}}
]

Brand name: {brand_name}
Slogan: "{subtitle}"
Industry: {industry}
Style: {style}
Additional notes: {additional_notes}

Generate exactly 4 variants.
"""

    slogan_responses = []

    try:
        result = AIService.generate(
            feature="branding",
            user_input=slogan_prompt,
            temperature=0.7,
            max_tokens=500
        )

        slogan_text = result.get("response", "")

        # Convert AIService response → existing extractor format
        slogan_responses = extract_text_from_response(
            {
                "output": [
                    {
                        "content": [
                            {"type": "output_text", "text": slogan_text}
                        ]
                    }
                ]
            },
            expect_json=True,
            strict=True
        )

        if not slogan_responses:
            raise ValueError("Empty slogan response")

    except Exception as e:
        return jsonify({"error": f"Slogan generation failed: {str(e)}"}), 500

    # =========================
    # 🔹 IMAGE GENERATION (UNCHANGED)
    # =========================

    client = get_openai_client()

    prompt = f"""
You are a world-class brand identity designer creating a professional startup logo.

TASK:
Create a PREMIUM vector logo SYMBOL (ICON ONLY).
NO text. NO letters. NO slogan.

BRAND CONTEXT:
- Brand name: "{brand_name}"
- Industry: {industry}
- Style direction: {style}
- Symbol concept: {symbol}
- Color palette: {", ".join(colors) if colors else "black and white"}
- Additional notes: {additional_notes}

STRICT RULES:
- NO text
- NO letters
- NO numbers
- NO gradients
- NO shadows
- NO 3D

STYLE:
- Flat vector design
- Clean geometric shapes
- Minimal
"""

    try:
        response = client.images.generate(
            model="gpt-image-1",
            prompt=prompt,
            size="1024x1024",
            n=IMAGE_COUNT,
            background="transparent"
        )
    except Exception as e:
        return jsonify({"error": str(e)}), 500

    images = []

    for img in response.data:
        images.append({
            "id": str(uuid.uuid4()),
            "base64": img.b64_json
        })

    user.wallet.spend_credits(
        amount=total_cost,
        description=f"Generated {IMAGE_COUNT} logo images"
    )

    db.session.commit()

    return jsonify({
        "success": True,
        "cost": total_cost,
        "images": images,
        "slogan_designs": slogan_responses
    }), 200

@ai_bp.route("/assistant/documents", methods=["POST"])
@jwt_required()
def upload_document():
    
    user_id = get_jwt_identity()
    user = User.query.get(user_id)

    if not user or not user.is_admin():
        return {
            "success": False,
            "error": "You are not authorized to upload documents"
        }, 403
    if "file" not in request.files:
        return {"error": "No file provided"}, 400
    user_id = get_jwt_identity()
    user = User.query.get(user_id)
    if not user.is_admin():
        return {"error": "Unauthorized"}, 403
    file = request.files["file"]
    if file.filename == "":
        return {"error": "Empty filename"}, 400

    if not file.filename.lower().endswith((".pdf", ".doc", ".docx")):
        return {"error": "Unsupported file type"}, 400

    upload_dir = current_app.config["UPLOAD_FOLDER"]
    os.makedirs(upload_dir, exist_ok=True)

    file_path = os.path.join(upload_dir, file.filename)
    file.save(file_path)

    result = ingest_document(file_path)

    return jsonify({
        "success": True,
        "message": "Document indexed successfully",
        "data": result
    })

@ai_bp.route("/assistant/query", methods=["POST"])
@jwt_required()
def assistant_query():
    data = request.get_json()

    if not data or "question" not in data:
        return standard_response(False, None, "Missing question", 400)

    question = data.get("question", "").strip()
    if not question:
        return standard_response(False, None, "Empty question", 400)

    answer = ask_assistant(question)
    print("Assistant answer:", answer)
    return standard_response(True, {
        "answer": answer
    })

@ai_bp.route("/image/text-to-image", methods=["POST", "OPTIONS"])
@jwt_required()
def text_to_image():
    if request.method == "OPTIONS":
        return standard_response(True, {}, code=200)

    user_id = get_jwt_identity()
    user = User.query.get(user_id)

    if not user:
        return standard_response(False, None, "Unauthorized", 401)

    data = request.get_json()
    prompt = data.get("prompt", "").strip()

    if not prompt:
        return standard_response(False, None, "Prompt is required", 400)

    COST_PER_IMAGE = 10

    if not total_credits(user) < COST_PER_IMAGE:
        return standard_response(False, None, "Not enough credits", 402)

    try:
        image_base64 = generate_image(prompt)
    except Exception as e:
        return standard_response(False, None, str(e), 500)

    user.wallet.spend_credits(
        amount=COST_PER_IMAGE,
        description="Generated AI image"
    )
    db.session.commit()

    return standard_response(True, {
        "cost": COST_PER_IMAGE,
        "image": {
            "base64": image_base64
        }
    })

# ==================================
# Generates social media captions using AI from text input or image + text input. Captions are optimized per platform and tone and
# return only caption text.
#
# Supported platforms: Instagram, LinkedIn, Twitter/X, Facebook, YouTube (community posts), TikTok
#
# Supported tones: casual, professional, inspiring, promotional, educational, storytelling, humorous, minimalist
# ==================================
@ai_bp.route('/generate/caption', methods=['POST'])
def generate_caption():
    try:
        if request.method == 'OPTIONS':
            return standard_response(True, {}, code=200)

        data = request.get_json()
        if not data:
            return standard_response(False, None, 'Missing data in request', 400)

        model = data.get('model', AVAILABLE_MODELS[0])
        content_type = data.get('content_type', 'text')
        platform = data.get('platform', 'Instagram')
        tone = data.get('tone', 'casual')
        temperature = data.get('temperature', 0.7)
        max_tokens = data.get('max_tokens', 200)

        prompt = data.get('prompt')

        if isinstance(prompt, list):
            prompt = "\n".join(map(str, prompt))
        elif not isinstance(prompt, str):
            prompt = str(prompt)

        if model not in AVAILABLE_MODELS:
            return standard_response(
                False, None, f'Model not available. Choose from: {AVAILABLE_MODELS}', 400
            )
        
        # ==================================
        # CAPTION-BASED SYSTEM PROMPTS
        # ==================================

        CAPTION_SYSTEM_PROMPTS = {
            "text": (
                "You are a professional social media copywriter.\n"
                "Generate short, catchy, platform-optimized captions.\n"
                "Rules:\n"
                "- Output only caption text\n"
                "- No explanations\n"
                "- Include emojis and hashtags where appropriate\n"
                "- Generate 3 variations\n"
            ),
            "image": (
                "You are a professional social media copywriter.\n"
                "Generate short, catchy, platform-optimized captions from the given image and optional context.\n"
                "Generate captions that visually match the image.\n"
                "Rules:\n"
                "- Do not mention the image explicitly\n"
                "- No analysis or explanations\n"
                "- Include emojis and hashtags\n"
                "- Generate 3 variations\n"
            )
        }

        # system_prompt = CAPTION_SYSTEM_PROMPTS[content_type]
        response_text = ""
        tokens_used = 0

        # =========================
        # TEXT-ONLY CAPTION
        # =========================
        if content_type == 'text':

            # user_prompt = (
            #     f"Platform: {platform}\n"
            #     f"Tone: {tone}\n"
            #     f"Input: {prompt}"
            # )

            final_prompt = f"""
Platform: {platform}
Tone: {tone}

Content:
{prompt}

Generate 3 caption variations.
"""

        result = AIService.generate(
            feature="caption",
            user_input=final_prompt,
            temperature=temperature,
            max_tokens=max_tokens
        )

        response_text = result.get("response", "")
        

        # =========================
        # IMAGE-BASED CAPTION
        # =========================
        
        # Disabled for now - will require more complex handling of image input and integration with vision models
        
        # if content_type == 'image':
        #     image_file = data.get('image')
        #     if not image_file:
        #         return standard_response(False, None, 'Image file required', 400)

        #     response_text, tokens_used = get_vision_response(
        #         model=model,
        #         system_prompt=system_prompt,
        #         user_prompt=user_prompt,
        #         image_file=image_file,
        #         temperature=temperature,
        #         max_tokens=max_tokens
        #     )

        # =========================
        # RESPONSE
        # =========================
        return standard_response(True, {
            "response": response_text,
            "model": model,
            "tokens_used": tokens_used,
            "content_type": content_type,
            "timestamp": datetime.utcnow().isoformat()
        })

    except Exception as e:
        logging.exception("Generation error")
        return standard_response(False, None, str(e), 500)

    except Exception as e:
        logging.exception("Caption generation failed")
        return standard_response(False, None, str(e), 500)


# @ai_bp.route("/logo/generate", methods=["POST", "OPTIONS"])
# @jwt_required()
# def generate_logo():
#     if request.method == "OPTIONS":
#         return standard_response(True, {}, code=200)

#     user_id = get_jwt_identity()
#     user = User.query.get(user_id)

#     if not user:
#         return jsonify({"error": "Unauthorized"}), 401

#     data = request.get_json()

#     brand_name = data.get("brandName")
#     industry = data.get("industry", "technology")
#     style = data.get("style", "minimal")
#     colors = data.get("colors", [])
#     additional_notes = data.get("additionalNotes", "")
#     subtitle = data.get("subtitle", "")
#     symbol = data.get("symbol", "abstract")

#     if not brand_name:
#         return jsonify({"error": "brandName is required"}), 400

#     LOGO_COUNT = 4
#     COST_PER_LOGO = 10
#     total_cost = LOGO_COUNT * COST_PER_LOGO

#     # if user.credits < total_cost:
#     #     return jsonify({"error": "Not enough credits"}), 402

#     palette = ", ".join(colors) if colors else "black and white"

#     prompt = f"""
# You are a professional logo designer.

# Generate {LOGO_COUNT} DIFFERENT LOGO SYMBOLS as PURE SVG.

# CRITICAL RULES:
# - DO NOT include any text
# - DO NOT include brand name
# - DO NOT include subtitle
# - DO NOT use <text> tags
# - SYMBOL / ICON ONLY
# - Flat
# - Vector
# - Minimal
# - Transparent background
# - Centered
# - Clean geometry
# - Use only <path>, <rect>, <circle>, <polygon>

# Brand context (for inspiration only):
# Name: {brand_name}
# Industry: {industry}
# Style: {style}
# Symbol idea: {symbol}
# Colors: {palette}

# Wrap each SVG between:
# <!-- LOGO START -->
# <!-- LOGO END -->
# """


#     client = get_openai_client()

#     try:
#         response = client.responses.create(
#             model="gpt-4.1-mini",
#             input=prompt
#         )
#     except Exception as e:
#         return jsonify({"error": str(e)}), 500

#     text_output = response.output_text or ""

#     # Extract SVG blocks
#     svg_blocks = re.findall(
#         r"<!-- LOGO START -->(.*?)<!-- LOGO END -->",
#         text_output,
#         re.DOTALL
#     )

#     images = []

#     for svg in svg_blocks[:LOGO_COUNT]:
#         images.append({
#             "id": str(uuid.uuid4()),
#             "svg": svg.strip()
#         })

#     if not images:
#         return jsonify({"error": "No SVGs generated"}), 500

#     # user.credits -= total_cost
#     # db.session.commit()

#     return jsonify({
#         "success": True,
#         "type": "svg",
#         "count": len(images),
#         "cost": total_cost,
#         "images": images
#     }), 200