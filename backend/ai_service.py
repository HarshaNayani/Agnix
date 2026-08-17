import os
import json
import requests
from groq import Groq
from dotenv import load_dotenv

load_dotenv()

# Initialize Groq client
api_key = os.getenv("GROQ_API_KEY")
TAVILY_API_KEY = os.getenv("TAVILY_API_KEY")

if not api_key:
    print("❌ ERROR: GROQ_API_KEY not found in .env file")
    client = None
else:
    client = Groq(api_key=api_key)
    print("✅ Groq client initialized")

MODEL = "openai/gpt-oss-120b"  # llama-3.3-70b-versatile was deprecated by Groq in June 2026

SYSTEM_PROMPT = (
    "You are Agnix, a helpful, friendly, and knowledgeable AI assistant. "
    "Respond in a conversational and engaging manner. Keep responses concise but informative. "
    "Use the web_search tool whenever the user asks about current events, today's date or time, "
    "recent news, prices, scores, or anything that may have changed after your training cutoff. "
    "Do not guess at real-time information — search for it instead."
)

# -------------------------------
# Tool definition (Groq / OpenAI-compatible function calling)
# -------------------------------
TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "web_search",
            "description": (
                "Search the live web for current, real-time information such as news, "
                "today's date, current events, prices, or facts that may have changed "
                "after the model's training cutoff."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "The search query to look up on the web."
                    }
                },
                "required": ["query"]
            }
        }
    }
]


def web_search(query: str) -> str:
    """Run a web search via Tavily and return a compact text summary for the model."""
    if not TAVILY_API_KEY:
        return "Web search is not configured. Ask the developer to add TAVILY_API_KEY to .env."

    try:
        resp = requests.post(
            "https://api.tavily.com/search",
            json={
                "api_key": TAVILY_API_KEY,
                "query": query,
                "max_results": 5,
                "include_answer": True
            },
            timeout=10
        )
        data = resp.json()

        parts = []
        if data.get("answer"):
            parts.append(f"Quick answer: {data['answer']}")

        for r in data.get("results", [])[:5]:
            title = r.get("title", "")
            content = (r.get("content") or "")[:250]
            url = r.get("url", "")
            parts.append(f"- {title}: {content} (Source: {url})")

        return "\n".join(parts) if parts else "No relevant results found."

    except Exception as e:
        print(f"🔥 WEB SEARCH ERROR: {str(e)}")
        return f"Web search failed: {str(e)[:150]}"


def _run_tool_call(tool_call_name: str, arguments_json: str) -> str:
    if tool_call_name == "web_search":
        try:
            args = json.loads(arguments_json) if arguments_json else {}
        except json.JSONDecodeError:
            args = {}
        return web_search(args.get("query", ""))
    return f"Unknown tool: {tool_call_name}"


def get_ai_response(messages):
    """
    Non-streaming version (kept for any code that still calls it directly).
    Supports one round of tool calling.
    """
    if not client:
        return "⚠️ Groq API key is missing. Please add GROQ_API_KEY to your .env file."

    try:
        formatted_messages = [{"role": "system", "content": SYSTEM_PROMPT}] + messages

        completion = client.chat.completions.create(
            messages=formatted_messages,
            model=MODEL,
            temperature=0.7,
            max_tokens=500,
            tools=TOOLS,
            tool_choice="auto"
        )

        msg = completion.choices[0].message

        if msg.tool_calls:
            formatted_messages.append(msg)
            for tc in msg.tool_calls:
                result = _run_tool_call(tc.function.name, tc.function.arguments)
                formatted_messages.append({
                    "role": "tool",
                    "tool_call_id": tc.id,
                    "content": result
                })

            final = client.chat.completions.create(
                messages=formatted_messages,
                model=MODEL,
                temperature=0.7,
                max_tokens=500
            )
            return final.choices[0].message.content

        return msg.content

    except Exception as e:
        print(f"🔥 GROQ API ERROR: {str(e)}")
        return f"⚠️ Error: {str(e)[:100]}"


def get_ai_response_stream(messages):
    """
    Streaming version — yields response chunks as they arrive from Groq.
    Supports web_search tool calling: if the model requests a search mid-stream,
    we accumulate the tool call, run the search, feed results back, then stream
    the final answer.
    """
    if not client:
        yield "⚠️ Groq API key is missing. Please add GROQ_API_KEY to your .env file."
        return

    try:
        formatted_messages = [{"role": "system", "content": SYSTEM_PROMPT}] + messages

        stream = client.chat.completions.create(
            messages=formatted_messages,
            model=MODEL,
            temperature=0.7,
            max_tokens=500,
            tools=TOOLS,
            tool_choice="auto",
            stream=True
        )

        tool_calls_acc = {}
        saw_tool_call = False

        for chunk in stream:
            delta = chunk.choices[0].delta

            if getattr(delta, "tool_calls", None):
                saw_tool_call = True
                for tc in delta.tool_calls:
                    idx = tc.index
                    if idx not in tool_calls_acc:
                        tool_calls_acc[idx] = {"id": tc.id, "name": "", "arguments": ""}
                    if tc.id:
                        tool_calls_acc[idx]["id"] = tc.id
                    if tc.function and tc.function.name:
                        tool_calls_acc[idx]["name"] += tc.function.name
                    if tc.function and tc.function.arguments:
                        tool_calls_acc[idx]["arguments"] += tc.function.arguments

            if delta.content:
                yield delta.content

        if saw_tool_call and tool_calls_acc:
            tool_calls_list = [
                {
                    "id": tc["id"],
                    "type": "function",
                    "function": {"name": tc["name"], "arguments": tc["arguments"]}
                }
                for tc in tool_calls_acc.values()
            ]
            formatted_messages.append({
                "role": "assistant",
                "content": None,
                "tool_calls": tool_calls_list
            })

            for tc in tool_calls_acc.values():
                result = _run_tool_call(tc["name"], tc["arguments"])
                formatted_messages.append({
                    "role": "tool",
                    "tool_call_id": tc["id"],
                    "content": result
                })

            final_stream = client.chat.completions.create(
                messages=formatted_messages,
                model=MODEL,
                temperature=0.7,
                max_tokens=500,
                stream=True
            )
            for chunk in final_stream:
                delta = chunk.choices[0].delta.content
                if delta:
                    yield delta

    except Exception as e:
        print(f"🔥 GROQ STREAM ERROR: {str(e)}")
        yield f"⚠️ Error: {str(e)[:100]}"