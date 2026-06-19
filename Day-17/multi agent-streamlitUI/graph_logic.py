from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver
from typing import TypedDict, List, Annotated
import operator

from langchain_groq import ChatGroq
from langchain_community.tools.tavily_search import TavilySearchResults


class AgentState(TypedDict):
    task: str
    research_notes: Annotated[List[str], operator.add]
    draft: str
    next_node: str
    retry_count: int


def build_graph(groq_key: str, tavily_key: str):
    # Instantiate inside build_graph so they're in scope for all nodes
    llm = ChatGroq(
        model="llama-3.3-70b-versatile",
        api_key=groq_key,
        temperature=0
    )
    search = TavilySearchResults(tavily_api_key=tavily_key, k=2)

    # ---------- SUPERVISOR ----------
    def supervisor(state: AgentState):
        # No research yet → go research first
        if len(state["research_notes"]) == 0:
            return {"next_node": "researcher"}

        # Research done but no draft yet → analyze emotion
        if not state.get("draft"):
            return {"next_node": "emotion"}

        # Draft exists → done
        return {"next_node": "FINISH"}

    # ---------- RESEARCH ----------
    def researcher(state: AgentState):
        results = search.invoke(f"emotion psychology: {state['task']}")
        return {"research_notes": [str(results)]}

    # ---------- EMOTION ANALYSIS ----------
    def emotion_analyzer(state: AgentState):
        prompt = f"""
You are an emotion detection system.

Analyze this transcript:
{state['task']}

Use tone, word choice, and context.

Output:
- Primary Emotion (happy, sad, angry, neutral, anxious, etc.)
- Confidence (low / medium / high)
- Reason (1–2 sentences)
"""
        res = llm.invoke(prompt)
        return {"draft": res.content}

    # ---------- WRITER ----------
    def writer(state: AgentState):
        context = "\n".join(state["research_notes"])
        res = llm.invoke(f"""
Combine the research context and emotion analysis into a clear final report.

Transcript: {state['task']}
Research context: {context}
Current emotion analysis: {state.get('draft', '')}

Write a concise, structured emotion analysis report.
""")
        return {"draft": res.content}

    # ---------- BUILD GRAPH ----------
    builder = StateGraph(AgentState)

    builder.add_node("supervisor", supervisor)
    builder.add_node("researcher", researcher)
    builder.add_node("emotion", emotion_analyzer)
    builder.add_node("writer", writer)

    builder.set_entry_point("supervisor")

    builder.add_conditional_edges(
        "supervisor",
        lambda x: x["next_node"],
        {
            "researcher": "researcher",
            "emotion": "emotion",
            "writer": "writer",
            "FINISH": END,
        }
    )

    builder.add_edge("researcher", "supervisor")
    builder.add_edge("emotion", "writer")
    builder.add_edge("writer", "supervisor")  # supervisor will now route to FINISH

    return builder.compile(checkpointer=MemorySaver())