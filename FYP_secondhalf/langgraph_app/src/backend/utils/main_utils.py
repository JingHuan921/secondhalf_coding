import json
import os
import tempfile
import subprocess
import time
from .parse_uml import uml_portion
import re 

import os
import time
import tempfile
import subprocess
import asyncio


async def generate_plantuml_local(uml_code, plantuml_jar_name="plantuml-1-2025-4.jar"):
    """Generate PlantUML diagram using local PlantUML installation (async-safe)"""
    try:
        # Get the parent directory (one level up from where the Python script is located)
        script_dir = os.path.dirname(os.path.abspath(__file__))
        parent_dir = os.path.dirname(script_dir)

        #Absolute path to PlantUML jar 
        plantuml_jar_path = os.path.join(script_dir, plantuml_jar_name)

        # Create output directory in parent folder (offload to thread)
        output_dir = os.path.join(parent_dir, "output")
        await asyncio.to_thread(os.makedirs, output_dir, exist_ok=True)

        # Generate timestamp and filename
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        output_file = os.path.join(output_dir, f"diagram_{timestamp}.png")

        # Create a temporary file for the UML code (offload to thread)
        def _write_tempfile():
            with tempfile.NamedTemporaryFile(mode='w', suffix='.puml', delete=False) as temp_file:
                temp_file.write(uml_code)
                return temp_file.name

        temp_puml_path = await asyncio.to_thread(_write_tempfile)

        # Run PlantUML in a thread (subprocess.run is blocking)
        cmd = [
            'java', '-jar', plantuml_jar_path,
            '-tpng',  # Output format: PNG
            '-o', output_dir,  # Output directory (output folder in parent directory)
            temp_puml_path
        ]
        
        print("Using jar:", plantuml_jar_path, "Exists?", os.path.exists(plantuml_jar_path))

        result = await asyncio.to_thread(
            subprocess.run, cmd, capture_output=True, text=True, timeout=30
        )

        if result.returncode == 0:
            # PlantUML generates file with same name as temp file but .png extension
            base_name = os.path.splitext(os.path.basename(temp_puml_path))[0]
            generated_file = os.path.join(output_dir, f"{base_name}.png")

            if os.path.exists(generated_file):
                # Rename to our desired timestamped filename (offload to thread)
                await asyncio.to_thread(os.rename, generated_file, output_file)

                print(f"PlantUML diagram generated successfully: {output_file}")

                # Clean up temp file (offload to thread)
                await asyncio.to_thread(os.unlink, temp_puml_path)

                return output_file
            else:
                print(f"Expected output file not found: {generated_file}")

        else:
            print(f"PlantUML error: {result.stderr}")

        # Clean up temp file in case of error
        if os.path.exists(temp_puml_path):
            await asyncio.to_thread(os.unlink, temp_puml_path)

        return None

    except FileNotFoundError:
        print("Java or plantuml.jar not found. Please install Java and download plantuml.jar")
        return None
    except Exception as e:
        print(f"Error: {e}")
        return None


def load_prompts(filepath: str) -> dict:
    prompt_dict = {}

    with open(filepath, "r", encoding="utf-8") as f:
        for line in f:
            if line.strip():  # Skip empty lines
                data = json.loads(line)
                name = data.get("name")
                template = data.get("template")
                if name and template:
                    prompt_dict[name] = template
                else:
                    raise ValueError("Each line must contain 'name' and 'template' fields.")
    
    return prompt_dict

def extract_plantuml(text: str) -> str:
    """
    Extracts PlantUML content from a paragraph, including only the part from @startuml to @enduml.
    
    Args:
        text (str): The input paragraph that may contain PlantUML code
        
    Returns:
        str: The PlantUML code including @startuml and @enduml tags
        
    Raises:
        ValueError: If no PlantUML block is found in the text
    """
    # Use regex to find @startuml to @enduml block (case insensitive, multiline)
    pattern = r'@startuml.*?@enduml'
    match = re.search(pattern, text, re.IGNORECASE | re.DOTALL)
    
    if not match:
        raise ValueError("No PlantUML block found. Expected text to contain @startuml ... @enduml")
    
    return match.group(0)