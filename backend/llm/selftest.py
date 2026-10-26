"""Check the Groq connection once you have added GROQ_API_KEY to .env:
    .venv\\Scripts\\python -m backend.llm.selftest
"""
from datetime import date

from ..config import GROQ_MODEL_FAST, GROQ_MODEL_SMART
from . import groq_client, parser

if __name__ == "__main__":
    if not groq_client.available():
        print("No GROQ_API_KEY in .env - the app runs on the rule-based fallback.")
    else:
        for m in (GROQ_MODEL_FAST, GROQ_MODEL_SMART):
            out = groq_client.chat(m, "Reply with the single word: ready", "Status?", max_tokens=5)
            print(f"{m}: {'OK - ' + out.strip() if out else 'FAILED (check the key / model name in the Groq console)'}")
        reqs, src = parser.parse("Need 2 senior Java developers with Spring Boot and Kafka, 6+ years, from January. "
                                 "Payments experience is a plus.", date.today())
        print(f"parse via {src}: {reqs['headcount']} x {reqs['title']}, must={len(reqs['mandatory_skills'])} skills")
