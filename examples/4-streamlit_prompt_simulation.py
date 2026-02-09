"""Streamlit Demo - Progressive Disclosure Visualization

This Streamlit app visually demonstrates how Progressive Disclosure works in Agent Skills.
Using the actual Strands Agents SDK, you can see the process of receiving queries
and automatically performing Phase 1->2->3 sequentially in real-time.
"""

import sys
import time
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

import streamlit as st

from agentskills import (
    create_skill_tool,
    discover_skills,
    generate_skills_prompt,
    load_instructions,
    load_resource,
)

# Page configuration
st.set_page_config(
    page_title="Agent Skills - Progressive Disclosure Demo",
    page_icon="🚀",
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
if "tool_calls" not in st.session_state:
    st.session_state.tool_calls = []
if "current_phase" not in st.session_state:
    st.session_state.current_phase = "Phase 1"
if "system_prompt" not in st.session_state:
    st.session_state.system_prompt = ""


# Global variables for tool call tracking (using session_state in Streamlit)
def init_tracking():
    """Initialize tracking variables"""
    if "tracker" not in st.session_state:
        st.session_state.tracker = {
            "skill_calls": [],
            "file_read_calls": [],
            "prompt_content": {
                "initial_system_prompt": "",
                "tool_results": [],
            },
            "agent_responses": [],
            "current_query": "",
            "is_running": False,
        }






# Main title
st.title("🚀 Agent Skills - Progressive Disclosure Demo")
st.markdown("""
This demo visually demonstrates how the **Progressive Disclosure** pattern works.
You can see what is loaded at each Phase and how it's included in the Agent's prompt.
""")

# Sidebar
with st.sidebar:
    st.header("📋 Settings")
    
    skills_dir = Path(__file__).parent.parent / "skills"
    st.info(f"Skills directory: `{skills_dir}`")
    
    if st.button("🔄 Reload Skills", use_container_width=True, key="reload_skills"):
        st.session_state.skills = discover_skills(skills_dir)
        st.session_state.tool_calls = []
        st.session_state.current_phase = "Phase 1"
        init_tracking()
        st.rerun()
    
    st.divider()
    
    st.header("ℹ️ What is Progressive Disclosure?")
    st.markdown("""
    **Progressive Disclosure** is a pattern that loads only necessary information at the necessary time:
    
    1. **Phase 1**: Load only metadata (~100 tokens/skill)
    2. **Phase 2**: Load instructions when skill is used (~1000-5000 tokens)
    3. **Phase 3**: Load only necessary resources (variable)
    
    This is much more efficient than loading entire skills in advance!
    """)


# Phase 1: Discovery
def show_phase1():
    """Phase 1: Discovery visualization"""
    st.header("📦 Phase 1: Discovery (Metadata Only)")
    
    skills_dir = Path(__file__).parent.parent / "skills"
    
    if not st.session_state.skills:
        if st.button("🔍 Discover Skills", use_container_width=True, key="discover_skills"):
            with st.spinner("Scanning Skills directory..."):
                st.session_state.skills = discover_skills(skills_dir)
                init_tracking()
                st.rerun()
        return
    
    # Display Skills list
    col1, col2 = st.columns([2, 1])
    
    with col1:
        st.subheader("Discovered Skills")
        
        total_tokens = 0
        for i, skill in enumerate(st.session_state.skills, 1):
            metadata_text = (
                f"{skill.name} {skill.description} "
                f"{skill.license or ''} {skill.compatibility or ''} "
                f"{skill.allowed_tools or ''}"
            )
            tokens = estimate_tokens(metadata_text)
            total_tokens += tokens
            
            with st.expander(f"📦 {skill.name}", expanded=(i == 1)):
                st.write(f"**Description:** {skill.description}")
                st.write(f"**Path:** `{skill.path}`")
                if skill.allowed_tools:
                    st.write(f"**Allowed tools:** {skill.allowed_tools}")
                st.metric("Estimated tokens", f"~{tokens} tokens")
        
        st.divider()
        st.metric("Total tokens (Phase 1)", f"~{total_tokens} tokens", f"{len(st.session_state.skills)} skills")
    
    with col2:
        st.subheader("Phase 1 Summary")
        st.info(f"""
        ✅ **{len(st.session_state.skills)}** Skills discovered
        
        📊 **Token usage:**
        - Total: ~{total_tokens} tokens
        - Average: ~{total_tokens // len(st.session_state.skills) if st.session_state.skills else 0} tokens/skill
        
        💡 **Included content:**
        - ✅ Skill name
        - ✅ Description
        - ✅ Path (location)
        - ❌ Instructions (not yet)
        - ❌ Resources (not yet)
        """)
    
    # Generate and display System Prompt
    st.divider()
    st.subheader("Generated System Prompt (Phase 1)")
    
    base_prompt = "You are a helpful AI assistant."
    skills_prompt = generate_skills_prompt(st.session_state.skills)
    full_prompt = f"{base_prompt}\n\n{skills_prompt}"
    
    st.session_state.system_prompt = full_prompt
    st.session_state.tracker["prompt_content"]["initial_system_prompt"] = full_prompt
    
    prompt_tokens = estimate_tokens(full_prompt)
    
    col1, col2 = st.columns([3, 1])
    with col1:
        st.code(full_prompt, language="markdown")
    with col2:
        st.metric("Prompt size", f"~{format_number(prompt_tokens)} tokens")
        st.metric("Character count", f"{len(full_prompt):,}")
    

# Phase 2: Activation
def show_phase2():
    """Phase 2: Activation visualization"""
    st.header("🎯 Phase 2: Activation (Load Instructions)")
    
    if not st.session_state.skills:
        st.warning("Please discover Skills in Phase 1 first.")
        if st.button("⬅️ Go back to Phase 1", key="back_to_phase1_from_phase2"):
            st.session_state.current_phase = "Phase 1"
            st.rerun()
        return
    
    # Generate System Prompt
    base_prompt = "You are a helpful AI assistant."
    skills_prompt = generate_skills_prompt(st.session_state.skills)
    full_prompt = f"{base_prompt}\n\n{skills_prompt}"
    
    if not st.session_state.tracker["prompt_content"]["initial_system_prompt"]:
        st.session_state.tracker["prompt_content"]["initial_system_prompt"] = full_prompt
    
    # Skill activation simulation
    st.subheader("Skill Activation Simulation")
    st.info("💡 **Phase 2:** When you select a Skill, Instructions are loaded and added to the Prompt!")
    
    skill_names = [s.name for s in st.session_state.skills]
    selected_skill = st.selectbox(
        "Select Skill to activate:",
        skill_names,
        key="skill_selector_phase2",
        index=0 if "web-research" in skill_names else None
    )
    
    if st.button("🎯 Simulate Skill Activation", use_container_width=True, type="primary", key="simulate_skill_activation"):
        skills_dir = Path(__file__).parent.parent / "skills"
        skill_tool = create_skill_tool(st.session_state.skills, skills_dir)
        result = skill_tool(selected_skill)
        
        # Tracking
        if "tracker" in st.session_state:
            st.session_state.tracker["skill_calls"].append({
                "skill_name": selected_skill,
                "phase": 2,
                "timestamp": time.time(),
            })
            st.session_state.tracker["prompt_content"]["tool_results"].append({
                "type": "skill",
                "skill_name": selected_skill,
                "content": result,
                "tokens": estimate_tokens(result),
            })
        
        if result:
            st.success(f"✅ {selected_skill} Skill activated! Instructions loaded.")
            st.rerun()
    
    # Tool call tracking display
    if st.session_state.tracker["skill_calls"]:
        st.divider()
        st.subheader("🔧 Tool Call Tracking")
        
        for i, call in enumerate(st.session_state.tracker["skill_calls"], 1):
            skill_name = call["skill_name"]
            with st.expander(f"Call #{i}: skill('{skill_name}')", expanded=True):
                # Load the skill's instructions
                skill = next((s for s in st.session_state.skills if s.name == skill_name), None)
                if skill:
                    instructions = load_instructions(skill.path)
                    tokens = estimate_tokens(instructions)
                    
                    col1, col2 = st.columns([2, 1])
                    with col1:
                        st.code(instructions, language="markdown")
                    with col2:
                        st.metric("Instructions tokens", f"~{format_number(tokens)} tokens")
                        st.metric("Instructions size", f"{len(instructions):,} chars")
        
        # Calculate current prompt state
        st.divider()
        st.subheader("📋 Current Prompt State")
        
        initial_tokens = estimate_tokens(st.session_state.tracker["prompt_content"]["initial_system_prompt"])
        tool_tokens = sum(r.get("tokens", 0) for r in st.session_state.tracker["prompt_content"]["tool_results"])
        total_tokens = initial_tokens + tool_tokens
        
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("System Prompt", f"~{format_number(initial_tokens)} tokens")
        with col2:
            st.metric("Tool results", f"~{format_number(tool_tokens)} tokens")
        with col3:
            st.metric("Total Prompt", f"~{format_number(total_tokens)} tokens")
    
    # Prompt content display
    with st.expander("📄 View full Prompt content", expanded=False):
        st.write("**System Prompt (Phase 1):**")
        st.code(st.session_state.tracker["prompt_content"]["initial_system_prompt"], language="markdown")
        
        for i, result in enumerate(st.session_state.tracker["prompt_content"]["tool_results"], 1):
            st.write(f"**Tool result #{i} ({result.get('type', 'unknown')}):**")
            content = str(result.get("content", ""))
            st.code(content, language="markdown")
    

# Phase 3: Resources
def show_phase3():
    """Phase 3: Resources visualization"""
    st.header("📚 Phase 3: Resources (Load as needed)")
    
    if not st.session_state.skills:
        st.warning("Please discover Skills in Phase 1 first.")
        if st.button("⬅️ Go back to Phase 1", key="back_to_phase1_from_phase3"):
            st.session_state.current_phase = "Phase 1"
            st.rerun()
        return
    
    # Display available resources
    st.subheader("Available Resources")
    
    # Find activated skill from Phase 2
    activated_skill_name = None
    if st.session_state.tracker["skill_calls"]:
        activated_skill_name = st.session_state.tracker["skill_calls"][-1]["skill_name"]
    
    # Select skill if no activated skill
    if not activated_skill_name:
        st.info("💡 After activating a skill in Phase 2, you can view its resources.")
        skill_names = [s.name for s in st.session_state.skills]
        selected_skill_name = st.selectbox(
            "Select Skill to view resources:",
            skill_names,
            key="skill_selector_phase3"
        )
        activated_skill_name = selected_skill_name
    
    # Find selected skill
    selected_skill = next((s for s in st.session_state.skills if s.name == activated_skill_name), None)
    if not selected_skill:
        st.warning(f"Cannot find {activated_skill_name} skill.")
        return
    
    if activated_skill_name and st.session_state.tracker["skill_calls"]:
        st.success(f"✅ {activated_skill_name} skill is activated.")
    
    skill_dir = Path(selected_skill.skill_dir)
    resources = []
    for subdir in ["scripts", "references", "assets"]:
        resource_dir = skill_dir / subdir
        if resource_dir.exists() and resource_dir.is_dir():
            files = list(resource_dir.rglob("*"))
            for file_path in files:
                if file_path.is_file():
                    rel_path = f"{subdir}/{file_path.relative_to(resource_dir)}"
                    resources.append((rel_path, file_path))
    
    if not resources:
        st.info("This skill has no resource files.")
    else:
        st.write(f"**{len(resources)}** resource files found:")
        for rel_path, file_path in resources:
            size = file_path.stat().st_size
            col1, col2 = st.columns([3, 1])
            with col1:
                st.write(f"📄 `{rel_path}`")
            with col2:
                st.write(f"{size:,} bytes")
    
    # Resource file read simulation
    st.divider()
    st.subheader("Resource File Read Simulation")
    st.info("💡 **Tip:** Select and read a resource file!")
    
    if resources:
        selected_resource = st.selectbox(
            "Select resource file to read:",
            [r[0] for r in resources],
            key="resource_selector"
        )
        
        if st.button("📄 Simulate Resource File Read", use_container_width=True, type="primary", key="simulate_file_read"):
            # Find selected resource's information
            selected_info = next((r for r in resources if r[0] == selected_resource), None)
            if selected_info:
                rel_path, file_path = selected_info
                # Use load_resource
                try:
                    result = load_resource(selected_skill.skill_dir, rel_path)
                except Exception as e:
                    result = f"Error reading file: {str(e)}"
                
                # Tracking
                if "tracker" in st.session_state:
                    file_path_str = str(file_path)
                    st.session_state.tracker["file_read_calls"].append({
                        "path": file_path_str,
                        "rel_path": rel_path,
                        "phase": 3,
                        "timestamp": time.time(),
                    })
                    st.session_state.tracker["prompt_content"]["tool_results"].append({
                        "type": "file_read",
                        "path": file_path_str,
                        "rel_path": rel_path,
                        "content": result,
                        "tokens": estimate_tokens(result),
                    })
                
                if result:
                    st.success("✅ Resource file loaded!")
                    st.rerun()
    
    # File read call tracking
    if st.session_state.tracker["file_read_calls"]:
        st.divider()
        st.subheader("🔧 File Read Call Tracking")
        
        for i, call in enumerate(st.session_state.tracker["file_read_calls"], 1):
            path = call["path"]
            # Find file content from tracker
            file_result = next(
                (r for r in st.session_state.tracker["prompt_content"]["tool_results"] 
                 if r.get("type") == "file_read" and (r.get("path") == path or r.get("rel_path") == call.get("rel_path"))),
                None
            )
            
            with st.expander(f"Call #{i}: file_read('{path}')", expanded=True):
                if file_result:
                    content = file_result.get("content", "")
                    tokens = file_result.get("tokens", 0)
                    
                    col1, col2 = st.columns([2, 1])
                    with col1:
                        st.code(content, language="markdown")
                    with col2:
                        st.metric("Resource tokens", f"~{format_number(tokens)} tokens")
                        st.metric("Resource size", f"{len(content):,} chars")
                else:
                    st.warning("Cannot find file content.")
    
    # Final Prompt state
    st.divider()
    st.subheader("📋 Final Prompt State")
    
    initial_tokens = estimate_tokens(st.session_state.tracker["prompt_content"]["initial_system_prompt"])
    tool_tokens = sum(r.get("tokens", 0) for r in st.session_state.tracker["prompt_content"]["tool_results"])
    total_tokens = initial_tokens + tool_tokens
    
    # Token usage visualization
    col1, col2 = st.columns([2, 1])
    
    with col1:
        try:
            import plotly.graph_objects as go
            
            fig = go.Figure(data=[
            go.Bar(
                name="System Prompt",
                x=["Phase 1"],
                y=[initial_tokens],
                marker_color='#1f77b4',
            ),
            go.Bar(
                name="Tool Results",
                x=["Phase 2-3"],
                y=[tool_tokens],
                marker_color='#ff7f0e',
            ),
        ])
        
            fig.update_layout(
                title="Token Usage Comparison",
                xaxis_title="Phase",
                yaxis_title="Token Count",
                barmode='stack',
                height=300,
            )
            
            st.plotly_chart(fig, use_container_width=True)
        except ImportError:
            st.info("📊 Plotly is not installed, chart cannot be displayed. Install with `pip install plotly`.")
    
    with col2:
        st.metric("System Prompt", f"~{format_number(initial_tokens)} tokens")
        st.metric("Tool results", f"~{format_number(tool_tokens)} tokens")
        st.metric("Total Prompt", f"~{format_number(total_tokens)} tokens", delta=f"{len(st.session_state.tracker['prompt_content']['tool_results'])} tool calls")
    
    # Progressive Disclosure summary
    st.divider()
    st.subheader("💡 Progressive Disclosure Summary")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.success("""
        **Phase 1: Discovery**
        - ✅ Load only metadata
        - ✅ Minimal token usage
        - ✅ All skill information included
        """)
    
    with col2:
        st.info("""
        **Phase 2: Activation**
        - ✅ Load instructions only when needed
        - ✅ Added only on skill tool call
        - ✅ Selective loading
        """)
    
    with col3:
        st.warning("""
        **Phase 3: Resources**
        - ✅ Load only necessary resources
        - ✅ Added only on file_read call
        - ✅ Minimal context usage
        """)
    


# Main logic
def main():
    """Main function"""
    init_tracking()
    
    # Phase selection
    phase = st.session_state.current_phase
    
    # Phase tabs
    tab1, tab2, tab3 = st.tabs(["📦 Phase 1: Discovery", "🎯 Phase 2: Activation", "📚 Phase 3: Resources"])
    
    with tab1:
        show_phase1()
    
    with tab2:
        show_phase2()
    
    with tab3:
        show_phase3()
    
    # Bottom summary
    st.divider()
    st.markdown("""
    ### 🎯 Advantages of Progressive Disclosure
    
    1. **Token efficiency**: Load only necessary information at the necessary time to minimize token usage
    2. **Reduced decision-making complexity**: Agent doesn't need to see full content of all skills at once
    3. **Scalability**: Initial loading cost doesn't increase significantly even with many Skills
    4. **Natural usage**: Skills are activated only when the LLM determines they are necessary
    """)


if __name__ == "__main__":
    main()

