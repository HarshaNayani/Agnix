import os
from groq import Groq
from dotenv import load_dotenv

load_dotenv()

# Initialize Groq client
api_key = os.getenv("GROQ_API_KEY")

if not api_key:
    print("❌ ERROR: GROQ_API_KEY not found in .env file")
    client = None
else:
    client = Groq(api_key=api_key)
    print("✅ Groq client initialized")

def get_ai_response(messages):
    """
    Get response from Groq API using Llama 3.3 (free & fast)
    """
    if not client:
        return "⚠️ Groq API key is missing. Please add GROQ_API_KEY to your .env file."

    try:
        # Add system message for context
        system_message = {
            "role": "system",
            "content": "You are Agnix, a helpful, friendly, and knowledgeable AI assistant. Respond in a conversational and engaging manner. Keep responses concise but informative."
        }
        
        # Prepare messages (system + conversation history)
        formatted_messages = [system_message] + messages
        
        print(f"Sending {len(formatted_messages)} messages to Groq API")

        # Call Groq API (using Llama 3.3 70B model - free tier)
        chat_completion = client.chat.completions.create(
            messages=formatted_messages,
            model="llama-3.3-70b-versatile",  # Free model, very fast
            temperature=0.7,
            max_tokens=500
        )

        response = chat_completion.choices[0].message.content
        print(f"✅ AI Response received: {response[:50]}...")
        return response

    except Exception as e:
        print(f"🔥 GROQ API ERROR: {str(e)}")
        return f"⚠️ Error: {str(e)[:100]}"