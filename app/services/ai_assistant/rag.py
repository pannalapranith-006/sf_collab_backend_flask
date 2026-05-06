
HARDCODED_FAQ = {
    "what is sfcollab": "SFCollab is a startup operating system that unifies execution, real-time collaboration, operations, and AI-assisted workflows into one continuous platform — built for founders, builders, and teams who want to move fast.",
    "what is sf collab": "SFCollab is a startup operating system that unifies execution, real-time collaboration, operations, and AI-assisted workflows into one continuous platform — built for founders, builders, and teams who want to move fast.",
    "tell me about sfcollab": "SFCollab is an all-in-one platform where startups are born and scaled. From idea validation to investor readiness, it brings together collaboration, AI tools, a creative suite, and a gamified community — all in one place.",
    "what does sfcollab do": "SFCollab helps you turn raw ideas into structured startups. You can generate business plans, build pitch decks, collaborate with your team in real time, connect with investors, and access AI-powered tools — without switching between apps.",

    "who is sfcollab for": "SFCollab is built for startup founders, builders, developers, designers, and anyone looking to launch or join a startup. Whether you have an idea or are looking for a team, SFCollab is your starting point.",
    "who can use sfcollab": "Anyone building or joining a startup — solo founders, co-founders, developers, designers, mentors, and investors. SFCollab connects all of them in one ecosystem.",

    "features": "SFCollab offers: AI-powered business plan and pitch deck generation, real-time team collaboration, a virtual economy with XP and SF Coins, legal document automation, investor CRM, market research AI, a professional creative suite (logo generator, image editor, PDF signing), and smart talent/investor matching.",
    "key features": "SFCollab offers: AI-powered business plan and pitch deck generation, real-time team collaboration, a virtual economy with XP and SF Coins, legal document automation, investor CRM, market research AI, a professional creative suite (logo generator, image editor, PDF signing), and smart talent/investor matching.",
    "what can i do": "You can build a business plan, create AI pitch decks, plan your MVP, collaborate with your team on an infinite canvas, discover talent and investors, earn XP and SF Coins, and manage your startup's operations — all inside SFCollab.",

    "collaboration": "SFCollab features a real-time canvas with sub-50ms sync, so your entire team stays in perfect alignment — no refresh, no delay, no friction. It's built for distributed teams working across time zones.",
    "real time": "SFCollab's real-time execution engine syncs every action instantly across teams, boards, and workflows. Latency is under 50ms with 100% uptime SLA and infinite canvas scale.",
    "team": "You can build and manage your team directly on SFCollab — invite members, assign roles, track contributions, and collaborate on a shared infinite workspace in real time.",

    "create a startup": "Creating a startup on SFCollab is simple — fill in your idea, and the platform helps you structure it into a business plan, roadmap, and pitch deck automatically using AI.",
    "join a startup": "You can browse open positions at startups listed on SFCollab and apply directly. Startups post roles across technology, design, marketing, and more.",
    "find startup": "SFCollab's Startups section lists high-growth startups actively hiring. You can filter by stage, location, and industry to find the right fit.",

    "ai": "SFCollab includes advanced AI tools for business plan generation, pitch deck creation, market research, competitor analysis, financial modeling, risk assessment, and an AI interaction and voice control layer coming in Phase 1.",
    "pitch deck": "SFCollab can generate investor-ready AI pitch decks from your idea in minutes. Just provide your startup details and the AI structures it into a professional deck.",
    "business plan": "SFCollab's AI Business Plan Generator transforms your raw idea into a structured, detailed business plan — including roadmap, MVP planning, and smart milestones.",

    "xp": "SFCollab has a gamified XP system. You earn XP by contributing to projects, sharing knowledge, collaborating, and engaging with the community. XP helps you climb the leaderboard and unlock rewards.",
    "sf coins": "SF Coins are SFCollab's virtual currency. You earn them through contributions and can exchange them for premium features and rewards in the marketplace.",
    "gamification": "SFCollab has a full virtual economy — XP points, SF Coins, achievements, and a reward marketplace. The more you contribute, the more you unlock.",

    "pricing": "SFCollab is currently in early access. You can join the waitlist for free — no credit card required — and get full platform access when it launches.",
    "cost": "Joining SFCollab's waitlist is free. No credit card required. Full platform access is included with no hidden charges at signup.",
    "free": "Yes, you can join SFCollab for free by signing up on the waitlist. No credit card needed and you get full platform access.",
    "waitlist": "You can join SFCollab's waitlist directly on the website. It's free, no credit card required, and you get full platform access once onboarded.",
    "subscription": "SFCollab is currently offering free waitlist access. Detailed subscription and pricing plans will be announced closer to the full launch.",

    "vision": "Visions are startup ideas posted by community members looking for collaborators. You can browse visions, vote on them, join discussions, and get involved to help bring them to life.",
    "collaborate": "You can collaborate on SFCollab by joining existing startups, contributing to community visions, forming teams, and connecting with founders and investors through smart matching.",

    "roadmap": "SFCollab is rolling out in 3 phases — Phase 0 (MVP): community, idea validation, team building. Phase 1: AI tools, mentorship, advanced collaboration. Phase 2: investor access, funding, automation, and a unified operating system.",
    "phase": "SFCollab's roadmap has 3 phases. Phase 0 focuses on community and idea validation. Phase 1 adds AI, mentorship, and advanced collaboration. Phase 2 brings investor access, secure funding, and full platform intelligence.",

    "contact": "You can reach SFCollab at sfcollab333@gmail.com or use the contact form on the website. The team responds within 24 hours.",
    "support": "For support, email sfcollab333@gmail.com or use the contact form on the SFCollab website. Expect a response within 24 hours.",
    "email": "You can contact SFCollab at sfcollab333@gmail.com. The team is happy to help with any questions or project inquiries.",
}

FALLBACK = "Sorry, I don't have an answer for that right now. For more help, reach out to us at sfcollab333@gmail.com and we'll get back to you within 24 hours."


def ask_assistant(question: str) -> str:

    q = question.lower().strip()

    for keyword, answer in HARDCODED_FAQ.items():
        if keyword in q:
            return answer

    return FALLBACK



# from sentence_transformers import SentenceTransformer
# from threading import Lock
# from groq import Groq
# from flask import current_app

# from app.services.ai_assistant.vector_store import get_collection
# from app.services.ai_assistant.prompts import ASSISTANT_SYSTEM_PROMPT
# import re

# _embedding_model = None
# _model_lock = Lock()

# def get_embedding_model():
#     global _embedding_model
#     if _embedding_model is None:
#         with _model_lock:
#             if _embedding_model is None:
#                 _embedding_model = SentenceTransformer(
#                     "sentence-transformers/all-MiniLM-L6-v2"
#                 )
#     return _embedding_model

# MAX_DISTANCE_THRESHOLD = 2.0
# TOP_K = 5
# FALLBACK = "Sorry, I don't know. Please ask something else."
# FALLBACK2 = "Something is wrong."

# def clean_llm_output(text: str) -> str:
#     text = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL)
#     return text.strip()

# def ask_assistant(question: str) -> str:
#     question = question.lower().strip()
#     embedding_model = get_embedding_model()
#     query_embedding = embedding_model.encode([question])[0].tolist()

#     collection = get_collection()
#     print("Total vectors:", collection.count())

#     results = collection.query(
#         query_embeddings=[query_embedding],
#         n_results=TOP_K,
#         include=["documents", "distances"]
#     )

#     documents = results.get("documents", [[]])[0]
#     distances = results.get("distances", [[]])[0]
#     print("RAG documents:", documents)
#     print("RAG distances:", distances)

#     if not documents or not distances:
#         return FALLBACK2

#     best_distance = distances[0]
#     if best_distance > MAX_DISTANCE_THRESHOLD:
#         return FALLBACK2

#     context = "\n\n".join(documents)

#     groq_client = Groq(api_key=current_app.config.get("GROQ_API_KEY"))

#     completion = groq_client.chat.completions.create(
#         model="qwen/qwen3-32b",
#         messages=[
#             {"role": "system", "content": ASSISTANT_SYSTEM_PROMPT},
#             {
#                 "role": "user",
#                 "content": f"Context:\n{context}\n\nQuestion:\n{question}"
#             }
#         ],
#         temperature=0,
#         max_tokens=512
#     )

#     raw_answer = completion.choices[0].message.content or ""
#     answer = clean_llm_output(raw_answer)
