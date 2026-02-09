"""Streamlit Meta-Tool Demo - Comparing Three Execution Modes

This Streamlit app visually compares three Agent Skills execution modes:
1. File-based Mode: LLM directly reads SKILL.md via file_read
2. Tool-based Mode: Load instructions via skill tool
3. Meta-Tool Mode: Use Sub-agent as tool (Agent as Tool pattern)
"""

import logging
import os
import sys
from pathlib import Path
from typing import Any

os.environ["BYPASS_TOOL_CONSENT"] = "true"
sys.path.insert(0, str(Path(__file__).parent.parent))

import streamlit as st
from strands import Agent
from strands.models import BedrockModel
from strands_tools import editor, file_read, file_write, shell

from agentskills import (
    create_skill_agent_tool,
    create_skill_tool,
    discover_skills,
    generate_skills_prompt,
    get_bedrock_agent_model,
)
from utils.strands_stream import StreamlitStreamRenderer
from utils.strands_stream.events import StreamOutput

# Logging configuration
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
)
logger = logging.getLogger(__name__)
logging.getLogger("opentelemetry.context").setLevel(logging.CRITICAL)

# Page configuration
st.set_page_config(
    page_title="Agent Skills - Multi-Agent Mode Demo",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="expanded",
)


# Helper functions removed - now handled by StreamlitStreamRenderer


def init_session_state():
    """Initialize session state"""
    if "skills" not in st.session_state:
        st.session_state.skills = []
    if "agent" not in st.session_state:
        st.session_state.agent = None
    if "mode" not in st.session_state:
        st.session_state.mode = "Meta-Tool Mode"


def create_agent_by_mode(skills, skills_dir, mode: str):
    """Create Agent according to selected mode"""
    skills_prompt = generate_skills_prompt(skills)
    
    agent_model = get_bedrock_agent_model(thinking=True)
    default_tools = [file_read, file_write, shell, editor]

    if mode == "File-based Mode":
        agent = Agent(
            system_prompt=skills_prompt,
            tools=default_tools,
            model=agent_model,
            callback_handler=None,
        )
        return agent

    elif mode == "Tool-based Mode":
        skill_tool = create_skill_tool(skills, skills_dir)

        agent = Agent(
            system_prompt=skills_prompt,
            tools=[skill_tool, *default_tools],
            model=agent_model,
            callback_handler=None,
        )
        return agent

    else:  # Meta-Tool Mode
        # Use Sub-agent as tool - Strands's "Agents as Tools" pattern
        subagent_model = get_bedrock_agent_model(
            max_tokens=48000,
            thinking=True
        )

        meta_tool = create_skill_agent_tool(
            skills,
            skills_dir,
            base_agent_model=subagent_model,
            additional_tools=default_tools
        )

        agent = Agent(
            system_prompt=skills_prompt,
            tools=[meta_tool],
            model=agent_model,
            callback_handler=None,
        )
        
        return agent


class StreamlitContainerManager:
    """Manage dynamic containers and expanders for different agent sources
    
    Uses hybrid rendering:
    - Main agent: Inline sections (new placeholder each time after sub-agent)
    - Sub-agents: Grouped by source (same sub-agent always uses same expander)
    """
    
    def __init__(self):
        self.sections = []  # List of all sections in order of appearance
        self.current_source: str | None = None  # Track current source
        self.current_section: dict | None = None  # Current active section
        self.subagent_sections: dict[str, dict] = {}  # Track sub-agent sections by source
    
    def append_content(self, source: str | None, content: str):
        """Append content to a section
        
        - Main agent (source=None): New section each time after sub-agent
        - Sub-agent: Reuse existing expander for same source, or create new one
        """
        if source is None:
            # Main agent - inline flow
            # Create new section if: first time, or current section is sub-agent
            if self.current_section is None or self.current_source != source:
                self.current_source = source
                placeholder = st.empty()
                self.current_section = {
                    "placeholder": placeholder,
                    "content": "",
                    "is_expander": False,
                    "source": None
                }
                self.sections.append(self.current_section)
                logger.debug("New main agent section created")
            
            # Append to current main agent section
            self.current_section["content"] += content
            if self.current_section["placeholder"]:
                self.current_section["placeholder"].markdown(self.current_section["content"])
        else:
            # Sub-agent - group by source
            self.current_source = source
            
            if source in self.subagent_sections:
                # Reuse existing expander for this sub-agent
                section = self.subagent_sections[source]
                section["content"] += content
                if section["placeholder"]:
                    section["placeholder"].markdown(section["content"])
                self.current_section = section
            else:
                # Create new expander for this sub-agent
                with st.expander(f"⚡ Sub-Agent: **{source}**", expanded=True):
                    placeholder = st.empty()
                    section = {
                        "placeholder": placeholder,
                        "content": content,
                        "is_expander": True,
                        "source": source
                    }
                    placeholder.markdown(content)
                
                self.subagent_sections[source] = section
                self.sections.append(section)
                self.current_section = section
                logger.debug(f"New sub-agent section created for: {source}")


async def render_agent_stream(agent_stream, container_manager: StreamlitContainerManager):
    """Render agent stream with source-based container management
    
    Process events using StreamlitStreamRenderer and render them
    in real-time streaming by source.
    """
    renderer = StreamlitStreamRenderer()

    try:
        async for event in agent_stream:
            if isinstance(event, dict):
                # Process event through renderer
                results = renderer.process(event)
                for result in results:
                    # Handle StreamOutput objects
                    if isinstance(result, StreamOutput):
                        if result.content:
                            source_label = result.source or "main agent"
                            logger.debug(f"Rendering content for {source_label}: {len(result.content)} chars")
                            container_manager.append_content(result.source, result.content)
                    # Handle legacy string outputs (for backward compatibility)
                    elif isinstance(result, str) and result:
                        # If we get a string, assume it's for main agent
                        logger.debug(f"Rendering legacy string for main agent: {len(result)} chars")
                        container_manager.append_content(None, result)

        logger.info("✅ Agent execution complete")

    except Exception as e:
        logger.error(f"Streaming error: {str(e)}")
        error_msg = f"\n\n❌ Error occurred: {str(e)}\n"
        container_manager.append_content(None, error_msg)
        raise


# Main UI
st.title("🤖 Strands AgentSkills")
st.subheader("🔍 Streamlit Integration Demo")
st.markdown("""> You can compare three Agent Skills execution modes and visually check the actual agent's SKILLS calling behavior.""")

# Initialize session state
init_session_state()

# Sidebar
with st.sidebar:
    st.header("⚙️ Settings")

    # Mode selection
    mode_options = ["Meta-Tool Mode", "Tool-based Mode", "File-based Mode"]
    selected_mode = st.selectbox(
        "Select execution mode:",
        mode_options,
        index=0,
        key="mode_select"
    )

    # Mode descriptions
    mode_descriptions = {
        "File-based Mode": "📄 LLM directly reads SKILL.md via file_read\n- Most natural approach\n- Recommended for general use",
        "Tool-based Mode": "🔧 Load instructions via skill tool\n- Structured approach\n- Explicit skill activation",
        "Meta-Tool Mode": "🔗 Use Sub-agent as tool\n- Agent as Tool pattern\n- Complete context separation"
    }

    st.info(mode_descriptions[selected_mode])

    st.divider()

    # Load Skills
    skills_dir = Path(__file__).parent.parent.parent / "skills"
    st.caption(f"Skills directory: `{skills_dir.name}`")

    if st.button("🔄 Reload Skills", use_container_width=True):
        with st.spinner("Loading Skills..."):
            st.session_state.skills = discover_skills(skills_dir)
            if st.session_state.skills:
                st.session_state.agent = create_agent_by_mode(
                    st.session_state.skills,
                    skills_dir,
                    selected_mode
                )
                st.session_state.mode = selected_mode
                st.success(f"✅ {len(st.session_state.skills)} Skills loaded!")
            else:
                st.warning("⚠️ Cannot find Skills.")
        st.rerun()

    # Recreate agent if mode changed
    if st.session_state.mode != selected_mode and st.session_state.skills:
        st.session_state.agent = create_agent_by_mode(
            st.session_state.skills,
            skills_dir,
            selected_mode
        )
        st.session_state.mode = selected_mode

    if st.session_state.skills:
        st.divider()
        st.subheader("📦 Discovered Skills")
        for skill in st.session_state.skills:
            with st.expander(f"**{skill.name}**"):
                st.caption(skill.description)
                st.caption(f"📁 `{Path(skill.path).parent.name}`")


# 메인 컨텐츠
if not st.session_state.skills:
    st.warning("⚠️ 사이드바에서 'Skills 다시 로드'를 클릭하여 Skills를 로드해주세요.")
    st.info("💡 Skills가 로드되면 질의를 입력하여 각 모드의 동작을 확인할 수 있습니다.")
else:
    # 현재 모드 표시
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("현재 모드", st.session_state.mode)
    with col2:
        st.metric("발견된 Skills", len(st.session_state.skills))
    with col3:
        status = "✅ 준비 완료" if st.session_state.agent else "❌ 미준비"
        st.metric("Agent 상태", status)

    st.divider()

    # 질의 입력
    st.header("💬 Agent 질의 실행")

    query = st.text_area(
        "질의 입력:",
        "Analyze the sales_data file and create it as an English pptx file with all visualization images attached. At the same time, write an insight analysis report in docs.",
        placeholder="Enter query for Agent",
        key="query_input",
        height="content"
    )

    run_button = st.button("🚀 Run", use_container_width=True, type="primary")

    # Execute Agent
    if run_button and query:
        # Display query
        with st.chat_message("user"):
            st.write(query)

        # Agent response
        with st.chat_message("assistant"):
            if hasattr(st.session_state.agent, "stream_async"):
                logger.info(f"🚀 Agent execution started [{st.session_state.mode}]: {query}")
                
                # Create container manager for source-based rendering
                container_manager = StreamlitContainerManager()
                
                # Handle Sub-agent streaming with Strands SDK's tool_stream_event pattern
                agent_stream = st.session_state.agent.stream_async(query)
                
                # Streamlit runs synchronously, so use asyncio.run()
                # If event loop is already running, solve with nest_asyncio
                import asyncio
                try:
                    import nest_asyncio
                    nest_asyncio.apply()
                except ImportError:
                    pass  # Works in most cases even without nest_asyncio
                
                asyncio.run(render_agent_stream(agent_stream, container_manager))
            else:
                st.error("This Agent does not support streaming.")

        st.success("✅ Execution complete!")


# Bottom information
st.divider()
st.caption("""
**💡 Tips:**
- Meta-Tool Mode: Agent as Tool pattern - Each Skill runs in an independent Sub-agent(tool)
- Tool-based Mode: You can see explicit activation through skill tool calls
- File-based Mode: Natural approach where LLM uses file_read tool to directly read SKILL.md
""")
