# agent.py (modify get_tools_async and other parts as needed)
import os
from dotenv import load_dotenv
from google.genai import types
from google.adk.agents.llm_agent import LlmAgent
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.adk.artifacts.in_memory_artifact_service import InMemoryArtifactService # Optional
from google.adk.tools.mcp_tool.mcp_toolset import MCPToolset, SseServerParams, StdioServerParameters
from pathlib import Path

root_dir = Path(__file__).resolve().parent.parent
load_dotenv(root_dir / '.env')

async def get_tools_async():
  """ Step 1: Gets tools from the Google Maps MCP Server."""
  # IMPORTANT: Replace with your actual key
  google_maps_api_key = os.getenv('GOOGLE_MAPS_API_KEY')
  if "YOUR_API_KEY" in google_maps_api_key:
      raise ValueError("Please replace 'YOUR_API_KEY_FROM_STEP_1' with your actual Google Maps API key.")

  print("Attempting to connect to MCP Google Maps server...")
  tools, exit_stack = await MCPToolset.from_server(
      connection_params=StdioServerParameters(
          command='npx',
          args=["-y",
                "@modelcontextprotocol/server-google-maps",
          ],
          # Pass the API key as an environment variable to the npx process
          env={
              "GOOGLE_MAPS_API_KEY": google_maps_api_key
          }
      )
  )
  print("MCP Toolset created successfully.")
  return tools, exit_stack

# --- Step 2: Agent Definition ---
async def get_agent_async():
  """Creates an ADK Agent equipped with tools from the MCP Server."""
  tools, exit_stack = await get_tools_async()
  print(f"Fetched {len(tools)} tools from Google Maps MCP server.")
  google_maps_agent = LlmAgent(
      model='gemini-2.0-flash', # Adjust if needed
      name='vegas_google_maps_agent',
      instruction='Help user with mapping and directions using available tools.',
      tools=tools,
  )
  # Return both the agent and the exit_stack
  return google_maps_agent, exit_stack
