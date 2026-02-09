"""Tool-Based usage example of Agent Skills

This example demonstrates the Tool-Based approach:
LLM uses the 'skill' tool to load instructions, then file_read for resources.

For Filesystem-Based approach, see: 1-basic_usage.py
"""

import asyncio
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from strands import Agent
from strands_tools import file_read

from agentskills import (
    create_skill_tool,
    discover_skills,
    generate_skills_prompt,
    get_bedrock_agent_model,
)
from utils.strands_stream import TerminalStreamRenderer


def estimate_tokens(text: str) -> int:
    """Rough token estimation (1 token ≈ 4 characters)"""
    return len(text) // 4


def print_section(title: str, phase: str = ""):
    """Print formatted section header"""
    print("\n" + "=" * 70)
    if phase:
        print(f"[{phase}] {title}")
    else:
        print(title)
    print("=" * 70)


async def main():
    """Tool-based usage example with progressive disclosure"""

    print_section("Progressive Disclosure: Tool-Based Usage", "")
    print("\n🎯 Progressive Disclosure: This approach minimizes context usage and maximizes efficiency")
    print("   1. Minimal initial load (Phase 1: metadata only)")
    print("   2. Load instructions only when skill is activated (Phase 2)")
    print("   3. Load resources only when actually needed (Phase 3)")
    
    # ========================================================================
    # Phase 1: Discovery - Load only metadata
    # ========================================================================
    print_section("Phase 1: Discovery (Metadata Only)", "PHASE 1")

    skills_dir = Path(__file__).parent.parent / "skills"
    print(f"\n📂 Scanning: {skills_dir}")
    print("⏳ Loading metadata only (no instructions or resources)...\n")

    skills = discover_skills(skills_dir)

    total_tokens = 0
    print(f"✅ Discovered {len(skills)} skills\n")

    for i, skill in enumerate(skills, 1):
        # Calculate approximate tokens for metadata
        metadata_text = (
            f"{skill.name} {skill.description} "
            f"{skill.license or ''} {skill.compatibility or ''} "
            f"{skill.allowed_tools or ''}"
        )
        tokens = estimate_tokens(metadata_text)
        total_tokens += tokens

        print(f"{i}. 📦 {skill.name}")
        print(f"   Description: {skill.description[:80]}...")
        print(f"   📊 Estimated tokens: ~{tokens} tokens")

        if skill.allowed_tools:
            print(f"   🔧 Allowed tools: {skill.allowed_tools}")
        if skill.compatibility:
            print(f"   ⚙️  Compatibility: {skill.compatibility}")

        print(f"   📁 Path: {skill.path}")
        print()

    if skills:
        print(f"💡 Phase 1 Total: ~{total_tokens} tokens for {len(skills)} skills")
        print(f"\n✓ Metadata loaded into system prompt (Phase 1 complete)")
        print(f"   ✓ Instructions not yet loaded (will load in Phase 2)")
        print(f"   ✓ Resources not yet loaded (will load in Phase 3)")

    if not skills:
        print("\n⚠️  No skills found. Create skills in 'skills/' directory.")
        return

    # ========================================================================
    # Phase 1: Generate system prompt with skill metadata
    # ========================================================================
    input("\n⏸  Press Enter to continue to generate system prompt...")
    print_section("Phase 1: Generate System Prompt", "PHASE 1.5")

    base_prompt = "You are a helpful AI assistant."
    skills_prompt = generate_skills_prompt(skills)
    full_prompt = f"{base_prompt}\n\n{skills_prompt}"

    prompt_tokens = estimate_tokens(full_prompt)
    print(f"\n📝 System prompt generated with skill metadata")
    print(f"   📊 System prompt size: {len(full_prompt)} characters")
    print(f"   📊 Estimated tokens: ~{prompt_tokens} tokens")
    print(f"   ✓ Contains metadata for {len(skills)} skills")
    print(f"\n📄 Generated system prompt:")
    print(full_prompt)

    # ========================================================================
    # Create agent with skill tool + file_read
    # ========================================================================
    input("\n⏸  Press Enter to continue to create agent...")
    print_section("Agent Initialization", "")

    skill_tool = create_skill_tool(skills, skills_dir)
    tool_name = getattr(skill_tool, '__name__', 'skill')
    print(f"\n🔧 Skill tool created: {tool_name}")
    print(f"   ✓ LLM can call this when instructions are needed")
    print(f"   ✓ Phase 2 triggered when LLM calls skill(skill_name=...)")

    agent_model = get_bedrock_agent_model()
    agent = Agent(
        system_prompt=full_prompt,
        tools=[skill_tool, file_read],
        model=agent_model,
        callback_handler=None,  # Disable default callback for custom streaming
    )

    print(f"\n✅ Agent created with:")
    print(f"   - System prompt (includes Phase 1 metadata)")
    print(f"   - skill tool (triggers Phase 2)")
    print(f"   - file_read tool (triggers Phase 3)")

    # ========================================================================
    # Example 1: Asking about available skills (Phase 1 only)
    # ========================================================================
    input("\n⏸  Press Enter to continue to example 1...")
    prompt = "Please describe the available skills."

    print_section(f"Question 1: {prompt}\n : This query uses Phase 1 metadata only (no skill tool call needed)", "")
    
    renderer = TerminalStreamRenderer()
    async for event in agent.stream_async(prompt):
        renderer.process(event)
    print()

    # ========================================================================
    # Example 2: LLM will use skill tool to load instructions (Phase 2)
    # ========================================================================
    input("\n⏸  Press Enter to continue to example 2...")

    if skills:
        prompt = f"How can I use the {skills[0].name} skill?"
        print_section(f"Question 2: {prompt}\n : This query triggers Phase 2 (skill tool call)", "")

        renderer.reset()
        async for event in agent.stream_async(prompt):
            renderer.process(event)
        
        print()


if __name__ == "__main__":
    asyncio.run(main())
