import asyncio
import os
from dotenv import load_dotenv
from openai import OpenAI
from pydantic import BaseModel

# Load your .env file so OpenAI gets the API key
load_dotenv()

# We need to import the Stips client we built
from src.scraper.client import StipsClient

# ---------------------------------------------------------
# 1. Stips API Test
# ---------------------------------------------------------
async def run_stips_test():
    print("\n[1] Testing Stips API Connection...")
    stips = StipsClient()
    try:
        # Using 445444 as a known test ID, or any active user ID
        user_id = 445444 
        meta = await stips.fetch_user_meta(user_id)
        print("✅ SUCCESS! Fetched User Meta:")
        print(f"   Nickname: {meta.get('nickname')}")
        print(f"   Flowers:  {meta.get('flower_count')}")
    except Exception as e:
        print(f"❌ STIPS ERROR: {e}")
    finally:
        await stips.close()


# ---------------------------------------------------------
# 2. OpenAI API Test (Structured Outputs & Embeddings)
# ---------------------------------------------------------
# A tiny Pydantic model just to prove the JSON forcing works
class MiniProfile(BaseModel):
    age: int
    hobbies: list[str]

def run_openai_test():
    print("\n[2] Testing OpenAI API (gpt-5.4-nano & embeddings)...")
    if not os.getenv("OPENAI_API_KEY"):
        print("❌ ERROR: OPENAI_API_KEY not found in .env file.")
        return

    client = OpenAI()

    try:
        # Test 1: Structured Output JSON Generation
        print("   -> Sending prompt to LLM...")
        completion = client.beta.chat.completions.parse(
            model="gpt-5.4-nano", 
            messages=[
                {"role": "user", "content": "I am 19 years old and I love playing guitar and gaming."}
            ],
            response_format=MiniProfile,
        )
        parsed_result = completion.choices[0].message.parsed
        print("✅ SUCCESS! LLM returned perfect Python object:")
        print(f"   Age: {parsed_result.age} | Hobbies: {parsed_result.hobbies}")

        # Test 2: Embeddings
        print("   -> Testing Vector Embeddings...")
        emb = client.embeddings.create(
            input=["Just a test sentence."], 
            model="text-embedding-3-small"
        )
        vector = emb.data[0].embedding
        print(f"✅ SUCCESS! Created embedding vector of length: {len(vector)}")

    except Exception as e:
        print(f"❌ OPENAI ERROR: {e}")
        if "model_not_found" in str(e).lower():
            print("\n💡 NOTE: If you get a 'model not found' error for gpt-5.4-nano, your API tier might not have access to it yet. Change it to 'gpt-4o-mini' in the code to test!")

# ---------------------------------------------------------
if __name__ == "__main__":
    asyncio.run(run_stips_test())
    run_openai_test()
    print("\nDone.\n")