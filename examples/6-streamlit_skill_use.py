"""Streamlit Demo - Agent Skills Effectiveness Comparison

This Streamlit app demonstrates the effectiveness of Agent Skills by allowing
side-by-side comparison of agent behavior with and without skills.
You can compare prompts, send queries, and see how skills enhance agent capabilities.
"""

import asyncio
import contextlib
import io
import sys
import time
import warnings
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

# Enable nested asyncio for Streamlit compatibility
try:
    import nest_asyncio
    nest_asyncio.apply()
except ImportError:
    pass  # Works in most cases even without nest_asyncio

import streamlit as st
from strands import Agent
from strands_tools import file_read, file_write, shell

from agentskills import (
    create_skill_tool,
    discover_skills,
    generate_skills_prompt,
    get_bedrock_agent_model,
)
from utils.strands_stream import StrandsEventParser
from utils.strands_stream.events import TextEvent

# Page configuration
st.set_page_config(
    page_title="Agent Skills - Effectiveness Demo",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded",
)


def estimate_tokens(text: str) -> int:
    """Rough token count estimation (1 token ≈ 4 characters)"""
    return len(text) // 4


def format_number(num: int) -> str:
    """Convert numbers to readable format"""
    if num >= 1000:
        return f"{num / 1000:.1f}K"
    return str(num)


# Initialize session state
if "skills" not in st.session_state:
    st.session_state.skills = []
if "agent_with_skills" not in st.session_state:
    st.session_state.agent_with_skills = None
if "agent_without_skills" not in st.session_state:
    st.session_state.agent_without_skills = None
if "chat_history_with" not in st.session_state:
    st.session_state.chat_history_with = []
if "chat_history_without" not in st.session_state:
    st.session_state.chat_history_without = []
if "comparison_mode" not in st.session_state:
    st.session_state.comparison_mode = "Side-by-side"


# Main title
st.title("⚡ Agent Skills - Effectiveness Demo")
st.markdown("""
Compare agent behavior **with** and **without** Agent Skills. See how skills enhance
agent capabilities, improve responses, and provide specialized knowledge.
""")

# Sidebar
with st.sidebar:
    st.header("⚙️ Configuration")
    
    # Skills directory
    skills_dir = Path(__file__).parent.parent / "skills"
    st.info(f"Skills directory: `{skills_dir}`")
    
    # Discover skills button
    if st.button("🔍 Discover Skills", use_container_width=True, key="discover_skills"):
        with st.spinner("Discovering skills..."):
            st.session_state.skills = discover_skills(skills_dir)
            st.session_state.agent_with_skills = None
            st.session_state.agent_without_skills = None
        st.success(f"Found {len(st.session_state.skills)} skills!")
        st.rerun()
    
    # Show discovered skills
    if st.session_state.skills:
        st.success(f"✅ {len(st.session_state.skills)} skills discovered")
        with st.expander("View Skills", expanded=False):
            for skill in st.session_state.skills:
                st.write(f"**{skill.name}**")
                st.caption(skill.description[:100] + "...")
    
    st.divider()
    
    # Comparison mode
    st.header("📊 Comparison Mode")
    st.session_state.comparison_mode = st.radio(
        "Select view:",
        ["Side-by-side", "With Skills Only", "Without Skills Only"],
        help="Choose how to view the agents"
    )
    
    st.divider()
    
    # Clear chat history
    if st.button("🗑️ Clear Chat History", use_container_width=True):
        st.session_state.chat_history_with = []
        st.session_state.chat_history_without = []
        st.rerun()
    
    st.divider()
    
    # Information
    st.header("ℹ️ About")
    st.markdown("""
    **Agent Skills** provide:
    - 🎯 Specialized knowledge
    - 📚 Domain expertise
    - 🔧 Task-specific workflows
    - 💡 Best practices
    - 🚀 Enhanced capabilities
    """)


def create_agents():
    """Create both agents (with and without skills)"""
    base_prompt = "You are a helpful AI assistant."
    
    # Agent WITHOUT skills
    if st.session_state.agent_without_skills is None:
        agent_model = get_bedrock_agent_model(thinking=False)
        st.session_state.agent_without_skills = Agent(
            system_prompt=base_prompt,
            tools=[file_read, file_write, shell],
            model=agent_model,
            callback_handler=None,
        )
    
    # Agent WITH skills
    if st.session_state.agent_with_skills is None and st.session_state.skills:
        skills_prompt = generate_skills_prompt(st.session_state.skills)
        full_prompt = f"{base_prompt}\n\n{skills_prompt}"
        
        skill_tool = create_skill_tool(st.session_state.skills, skills_dir)
        agent_model = get_bedrock_agent_model(thinking=False)
        
        st.session_state.agent_with_skills = Agent(
            system_prompt=full_prompt,
            tools=[skill_tool, file_read, file_write, shell],
            model=agent_model,
            callback_handler=None,
        )


def show_system_prompts():
    """Display system prompts comparison"""
    st.header("📝 System Prompt Comparison")
    
    base_prompt = "You are a helpful AI assistant."
    
    if st.session_state.comparison_mode == "Side-by-side":
        col1, col2 = st.columns(2)
        
        with col1:
            st.subheader("Without Skills")
            st.metric("Prompt size", f"~{estimate_tokens(base_prompt)} tokens")
            with st.expander("View prompt", expanded=False):
                st.code(base_prompt, language="markdown")
        
        with col2:
            st.subheader("With Skills")
            if st.session_state.skills:
                skills_prompt = generate_skills_prompt(st.session_state.skills)
                full_prompt = f"{base_prompt}\n\n{skills_prompt}"
                tokens = estimate_tokens(full_prompt)
                skill_metadata_tokens = estimate_tokens(skills_prompt)
                
                st.metric(
                    "Prompt size", 
                    f"~{format_number(tokens)} tokens",
                    delta=f"+{skill_metadata_tokens} from skills"
                )
                with st.expander("View prompt", expanded=False):
                    st.code(full_prompt, language="markdown")
            else:
                st.warning("No skills discovered yet")
    
    elif st.session_state.comparison_mode == "Without Skills Only":
        st.subheader("Without Skills")
        st.metric("Prompt size", f"~{estimate_tokens(base_prompt)} tokens")
        with st.expander("View prompt", expanded=True):
            st.code(base_prompt, language="markdown")
    
    else:  # With Skills Only
        st.subheader("With Skills")
        if st.session_state.skills:
            skills_prompt = generate_skills_prompt(st.session_state.skills)
            full_prompt = f"{base_prompt}\n\n{skills_prompt}"
            tokens = estimate_tokens(full_prompt)
            
            st.metric("Prompt size", f"~{format_number(tokens)} tokens")
            with st.expander("View prompt", expanded=True):
                st.code(full_prompt, language="markdown")
        else:
            st.warning("No skills discovered yet")


def show_chat_interface():
    """Display chat interface"""
    st.header("💬 Chat Interface")
    
    # Create agents if not already created
    create_agents()
    
    # Query input
    st.subheader("Ask a Question")
    
    # Suggested queries
    suggested_queries = [
        "What skills do you have?",
        "How can you help me?",
        "What are your capabilities?",
    ]
    
    # Add skill-specific suggestions if skills exist
    if st.session_state.skills:
        for skill in st.session_state.skills[:2]:  # First 2 skills
            suggested_queries.append(f"How do I use the {skill.name} skill?")
    
    # Check if any suggested query button was clicked
    query_to_process = None
    
    # Suggested queries as buttons (placed first so they can be clicked)
    st.write("**Suggested queries:**")
    cols = st.columns(min(len(suggested_queries), 3))  # Max 3 columns
    for i, query in enumerate(suggested_queries):
        with cols[i % len(cols)]:
            if st.button(query, key=f"suggested_{i}", use_container_width=True):
                query_to_process = query
    
    # Manual query input
    col1, col2 = st.columns([3, 1])
    with col1:
        user_query = st.text_input(
            "Your question:",
            placeholder="Type your question here...",
            key="user_query_input"
        )
    
    with col2:
        st.write("")  # Spacing
        st.write("")  # Spacing
        send_button = st.button("📤 Send", use_container_width=True, type="primary")
    
    # Process query from text input if Send button was clicked
    if send_button and user_query:
        query_to_process = user_query
    
    # Process the query if we have one
    if query_to_process:
        process_query(query_to_process)
        st.rerun()
    
    # Display chat history
    st.divider()
    show_chat_history()


async def get_agent_response(agent, query: str) -> str:
    """Get response from agent by collecting stream events"""
    response_parts = []
    complete_message = None  # Store the final complete message
    debug_mode = False  # Disable debug now that we know the structure
    
    try:
        async for raw_event in agent.stream_async(query):
            try:
                if debug_mode and isinstance(raw_event, dict):
                    print(f"DEBUG: Event keys: {raw_event.keys()}")
                
                # Raw events are dictionaries - extract text from various patterns
                if isinstance(raw_event, dict):
                    # Pattern 1: data key (streaming chunks)
                    if "data" in raw_event and isinstance(raw_event["data"], str):
                        text = raw_event["data"]
                        if text:
                            response_parts.append(text)
                            if debug_mode:
                                print(f"DEBUG: Got data chunk: {text[:50]}...")
                        continue
                    
                    # Pattern 2: contentBlockDelta -> delta -> text (streaming text chunks)
                    if "contentBlockDelta" in raw_event:
                        delta = raw_event.get("contentBlockDelta", {}).get("delta", {})
                        if isinstance(delta, dict) and "text" in delta:
                            text = delta["text"]
                            if text:
                                response_parts.append(text)
                                if debug_mode:
                                    print(f"DEBUG: Got text chunk: {text[:50]}...")
                            continue
                    
                    # Pattern 3: message key (complete final message)
                    if "message" in raw_event:
                        msg = raw_event.get("message", {})
                        if isinstance(msg, dict):
                            content_list = msg.get("content", [])
                            if isinstance(content_list, list):
                                for content_item in content_list:
                                    if isinstance(content_item, dict) and "text" in content_item:
                                        text = content_item["text"]
                                        if text and text.strip():
                                            # Store as complete message (use this if no chunks collected)
                                            complete_message = text
                                            if debug_mode:
                                                print(f"DEBUG: Got complete message: {text[:50]}...")
                                continue
                        
            except asyncio.CancelledError:
                break
            except Exception as e:
                if debug_mode:
                    print(f"DEBUG: Error processing event: {e}")
                continue
                    
    except asyncio.CancelledError:
        pass
    except Exception as e:
        return f"❌ Error: {str(e)}"
    
    # Prefer collected streaming chunks, fall back to complete message
    if response_parts:
        full_response = "".join(response_parts).strip()
    elif complete_message:
        full_response = complete_message.strip()
    else:
        full_response = ""
    
    return full_response if full_response else "No response received"


@contextlib.contextmanager
def suppress_otel_warnings():
    """Suppress OpenTelemetry context warnings in Streamlit"""
    with warnings.catch_warnings():
        warnings.filterwarnings("ignore", message=".*Failed to detach context.*")
        warnings.filterwarnings("ignore", message=".*was created in a different Context.*")
        yield


def process_query(query: str):
    """Process user query with both agents"""
    
    # Get or create event loop for Streamlit
    try:
        loop = asyncio.get_event_loop()
        if loop.is_closed():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    
    if st.session_state.comparison_mode in ["Side-by-side", "Without Skills Only"]:
        # Query without skills
        if st.session_state.agent_without_skills:
            with st.spinner("Agent without skills thinking..."):
                try:
                    # Temporarily suppress stderr for OpenTelemetry warnings
                    old_stderr = sys.stderr
                    sys.stderr = io.StringIO()
                    
                    with suppress_otel_warnings():
                        # Use the persistent event loop
                        response = loop.run_until_complete(
                            get_agent_response(st.session_state.agent_without_skills, query)
                        )
                    
                    sys.stderr = old_stderr
                    
                    st.session_state.chat_history_without.append({
                        "query": query,
                        "response": response,
                        "timestamp": time.time(),
                    })
                except Exception as e:
                    sys.stderr = old_stderr
                    st.error(f"Error (without skills): {str(e)}")
                    st.session_state.chat_history_without.append({
                        "query": query,
                        "response": f"❌ Error: {str(e)}",
                        "timestamp": time.time(),
                    })
        else:
            st.warning("Agent without skills not initialized. Please try again.")
    
    if st.session_state.comparison_mode in ["Side-by-side", "With Skills Only"]:
        # Query with skills
        if st.session_state.agent_with_skills:
            with st.spinner("Agent with skills thinking..."):
                try:
                    # Temporarily suppress stderr for OpenTelemetry warnings
                    old_stderr = sys.stderr
                    sys.stderr = io.StringIO()
                    
                    with suppress_otel_warnings():
                        # Use the persistent event loop
                        response = loop.run_until_complete(
                            get_agent_response(st.session_state.agent_with_skills, query)
                        )
                    
                    sys.stderr = old_stderr
                    
                    st.session_state.chat_history_with.append({
                        "query": query,
                        "response": response,
                        "timestamp": time.time(),
                    })
                except Exception as e:
                    sys.stderr = old_stderr
                    st.error(f"Error (with skills): {str(e)}")
                    st.session_state.chat_history_with.append({
                        "query": query,
                        "response": f"❌ Error: {str(e)}",
                        "timestamp": time.time(),
                    })
        elif not st.session_state.skills:
            st.warning("Please discover skills first using the 'Discover Skills' button in the sidebar.")
        else:
            st.warning("Agent with skills not initialized. Please try again.")


def show_chat_history():
    """Display chat history"""
    st.subheader("💭 Conversation History")
    
    if st.session_state.comparison_mode == "Side-by-side":
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown("**Without Skills**")
            if not st.session_state.chat_history_without:
                st.info("No messages yet. Send a query to start!")
            else:
                for i, item in enumerate(st.session_state.chat_history_without):
                    with st.container():
                        st.markdown(f"**You:** {item['query']}")
                        st.markdown(f"**Agent:** {item['response']}")
                        st.caption(f"Tokens: ~{estimate_tokens(item['response'])}")
                        if i < len(st.session_state.chat_history_without) - 1:
                            st.divider()
        
        with col2:
            st.markdown("**With Skills**")
            if not st.session_state.chat_history_with:
                st.info("No messages yet. Send a query to start!")
            else:
                for i, item in enumerate(st.session_state.chat_history_with):
                    with st.container():
                        st.markdown(f"**You:** {item['query']}")
                        st.markdown(f"**Agent:** {item['response']}")
                        st.caption(f"Tokens: ~{estimate_tokens(item['response'])}")
                        if i < len(st.session_state.chat_history_with) - 1:
                            st.divider()
    
    elif st.session_state.comparison_mode == "Without Skills Only":
        if not st.session_state.chat_history_without:
            st.info("No messages yet. Send a query to start!")
        else:
            for i, item in enumerate(st.session_state.chat_history_without):
                with st.container():
                    st.markdown(f"**You:** {item['query']}")
                    st.markdown(f"**Agent:** {item['response']}")
                    st.caption(f"Tokens: ~{estimate_tokens(item['response'])}")
                    if i < len(st.session_state.chat_history_without) - 1:
                        st.divider()
    
    else:  # With Skills Only
        if not st.session_state.chat_history_with:
            st.info("No messages yet. Send a query to start!")
        else:
            for i, item in enumerate(st.session_state.chat_history_with):
                with st.container():
                    st.markdown(f"**You:** {item['query']}")
                    st.markdown(f"**Agent:** {item['response']}")
                    st.caption(f"Tokens: ~{estimate_tokens(item['response'])}")
                    if i < len(st.session_state.chat_history_with) - 1:
                        st.divider()


def show_metrics():
    """Display comparison metrics"""
    st.header("📊 Comparison Metrics")
    
    if st.session_state.comparison_mode != "Side-by-side":
        st.info("Switch to 'Side-by-side' mode to see comparison metrics")
        return
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.metric(
            "Messages (Without Skills)",
            len(st.session_state.chat_history_without)
        )
    
    with col2:
        st.metric(
            "Messages (With Skills)",
            len(st.session_state.chat_history_with)
        )
    
    with col3:
        # Calculate average response length
        avg_without = 0
        if st.session_state.chat_history_without:
            avg_without = sum(
                len(item["response"]) 
                for item in st.session_state.chat_history_without
            ) // len(st.session_state.chat_history_without)
        
        avg_with = 0
        if st.session_state.chat_history_with:
            avg_with = sum(
                len(item["response"]) 
                for item in st.session_state.chat_history_with
            ) // len(st.session_state.chat_history_with)
        
        st.metric(
            "Avg Response Length",
            f"{avg_with} chars",
            delta=f"{avg_with - avg_without:+d} vs without skills"
        )


def main():
    """Main function"""
    
    # Show system prompts section
    show_system_prompts()
    
    st.divider()
    
    # Show chat interface
    show_chat_interface()
    
    st.divider()
    
    # Show metrics
    show_metrics()
    
    # Bottom information
    st.divider()
    st.markdown("""
    ### 💡 Key Observations
    
    When comparing agents **with** and **without** skills:
    
    1. **Knowledge**: Agent with skills has access to specialized domain knowledge
    2. **Capabilities**: Skills extend what the agent can do beyond basic tools
    3. **Context**: Skills provide relevant context and best practices
    4. **Guidance**: Skills offer structured workflows for complex tasks
    5. **Efficiency**: Skills help agent make better decisions faster
    
    Try asking domain-specific questions to see the difference!
    """)


if __name__ == "__main__":
    main()
