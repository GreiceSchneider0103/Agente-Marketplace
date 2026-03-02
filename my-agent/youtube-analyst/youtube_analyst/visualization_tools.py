import logging
import os

import plotly.express as px
import plotly.graph_objects as go
from google.adk.tools import ToolContext
from google.genai import types

logger = logging.getLogger(__name__)


async def execute_visualization_code(
    code: str, filename: str, tool_context: ToolContext = None
):
    """
    Executes Python code to generate a Plotly figure and saves it as an interactive HTML file.

    Args:
        code: Python code string. The code MUST define a variable named 'fig' which is a plotly.graph_objects.Figure.
              The code has access to 'go' (plotly.graph_objects) and 'px' (plotly.express).
        filename: The name of the file to save (e.g., 'chart.html').
        tool_context: The ADK tool context (automatically injected if available).

    Returns:
        The path to the saved HTML file or an error message.
    """
    try:
        # Create output directory if it doesn't exist
        output_dir = "output"
        if not os.path.exists(output_dir):
            os.makedirs(output_dir)

        if not filename.endswith(".html"):
            filename += ".html"

        filepath = os.path.join(output_dir, filename)

        # Execution environment
        local_vars = {}
        global_vars = {
            "go": go,
            "px": px,
            "print": print,
        }

        # Execute the code
        try:
            exec(code, global_vars, local_vars)
        except Exception as exec_error:
            return f"Error executing visualization code: {exec_error}"

        # Extract 'fig'
        fig = local_vars.get("fig")
        if not fig:
            # Fallback: check globals if user messed up scope (less likely with exec but possible)
            fig = global_vars.get("fig")

        if not fig:
            return "Error: The executed code did not define a variable named 'fig'."

        if not isinstance(fig, (go.Figure)):
            return f"Error: The variable 'fig' is not a plotly Figure. It is {type(fig)}."

        # Save as self-contained HTML
        fig.write_html(filepath, include_plotlyjs="cdn")

        if tool_context:
            try:
                with open(filepath, "rb") as f:
                    html_bytes = f.read()
                # Create a simple artifact name from filename
                artifact_name = filename.replace(".", "_").replace("-", "_")
                await tool_context.save_artifact(
                    artifact_name,
                    types.Part(
                        inline_data=types.Blob(
                            mime_type="text/html", data=html_bytes
                        )
                    ),
                )
                logger.info(f"Successfully saved artifact {filename}")
            except Exception as e:
                logger.warning(f"Warning: Failed to save artifact: {e}")

        return f"Interactive chart saved to {filename}"
    except Exception as e:
        return f"Error processing visualization: {e!s}"
