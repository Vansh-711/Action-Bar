import json
import os
import sys
from dotenv import load_dotenv
from groq import Groq

# Add parent dir to path so we can import groq_brain
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
import groq_brain

load_dotenv()
API_KEY = os.getenv("GROQ_API_KEY")
client = Groq(api_key=API_KEY)

# We use the smarter 70B model as the "Professor" to grade the Agent
JUDGE_MODEL = "llama-3.3-70b-versatile"

def grade_plan(prompt, agent_output, reference_logic):
    """
    Asks the Judge Model to rate the Agent's output against the reference logic.
    """
    judge_prompt = f"""You are a Senior Automation QA Engineer. 
Your job is to grade the performance of an AI Automation Agent.

USER PROMPT: {prompt}
REFERENCE LOGIC (GROUND TRUTH): {reference_logic}

AGENT'S GENERATED PLAN:
{json.dumps(agent_output, indent=2)}

GRADING CRITERIA:
1. Logic (0-50): Does it follow the Reference Logic? Does it handle dynamic data (loops/if) correctly?
2. Syntax (0-20): Is it valid JSON? Does it use the tools correctly?
3. Safety (0-30): Does it avoid hallucinations (clicking non-existent buttons)?

Output your response in this EXACT JSON format:
{{
  "logic_score": 0-50,
  "syntax_score": 0-20,
  "safety_score": 0-30,
  "total_score": 0-100,
  "feedback": "Why did you give this score?"
}}
"""
    try:
        completion = client.chat.completions.create(
            model=JUDGE_MODEL,
            messages=[{"role": "user", "content": judge_prompt}],
            response_format={"type": "json_object"}
        )
        return json.loads(completion.choices[0].message.content)
    except Exception as e:
        return {"error": str(e)}

def run_benchmark():
    print("🧪 Starting Automated Benchmark Suite...")
    
    with open("benchmarking/gold_standard_tests.json", "r") as f:
        tests = json.load(f)
    
    results = []

    for test in tests:
        print(f"\n📝 Testing: {test['id']}...")
        
        # 1. Get Agent's Plan
        agent_plan = groq_brain.get_action_plan(test['prompt'])
        
        if not agent_plan:
            print(f"❌ Agent failed to generate plan for {test['id']}")
            continue
            
        # 2. Grade it
        print("👨‍⚖️ Judging logic...")
        grade = grade_plan(test['prompt'], agent_plan, test['reference_logic'])
        
        results.append({
            "test_id": test['id'],
            "score": grade.get("total_score", 0),
            "feedback": grade.get("feedback", "No feedback")
        })
        
        print(f"⭐ Score: {grade.get('total_score')}/100")
        print(f"💬 Feedback: {grade.get('feedback')}")

    print("\n" + "="*30)
    print("📊 FINAL REPORT")
    avg_score = sum(r['score'] for r in results) / len(results)
    print(f"Average Agent Performance: {avg_score:.1f}/100")
    print("="*30)

if __name__ == "__main__":
    run_benchmark()
