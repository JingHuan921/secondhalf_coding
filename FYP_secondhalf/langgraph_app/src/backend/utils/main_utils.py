import json
import os
import tempfile
import subprocess
import time
import re 

import os
import time
import tempfile
import subprocess
import asyncio

from typing import Any, Dict, List, Union
from pydantic import BaseModel
import json
import base64

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

async def convert_pydantic_model_to_text(model: BaseModel, format_style: str = "readable") -> str:
    """
    Convert any Pydantic model to text using various formatting styles.
    
    Args:
        model: Any Pydantic BaseModel instance
        format_style: "readable", "json", "yaml", "compact", or "detailed"
    
    Returns:
        Formatted text representation of the model
    """
    
    if format_style == "json":
        return model.model_dump_json(indent=2)
    
    elif format_style == "json_compact":
        return model.model_dump_json()
    
    else:  # "readable" (default)
        return _format_readable(model.model_dump())
    

async def pydantic_to_json_text(model: BaseModel, indent: int = 2) -> str:
    """Convert Pydantic model to formatted JSON text"""
    try: 
        dumped_text = model.model_dump_json(indent=indent)
    except Exception as e: 
        print(f"Error with: {model}")
    return dumped_text


def _format_readable(data: Dict[str, Any], indent: int = 0) -> str:
    """Format data in a human-readable bullet-point style"""
    lines = []
    indent_str = "  " * indent
    
    for key, value in data.items():
        formatted_key = key.replace('_', ' ').title()
        
        if isinstance(value, dict):
            lines.append(f"{indent_str}• {formatted_key}:")
            lines.append(_format_readable(value, indent + 1))
        elif isinstance(value, list):
            lines.append(f"{indent_str}• {formatted_key}:")
            for i, item in enumerate(value, 1):
                if isinstance(item, dict):
                    lines.append(f"{indent_str}  {i}.")
                    lines.append(_format_readable(item, indent + 2))
                else:
                    lines.append(f"{indent_str}  {i}. {item}")
        else:
            lines.append(f"{indent_str}• {formatted_key}: {value}")
    
    return "\n".join(lines)

import os
import asyncio
import subprocess
import tempfile

async def generate_plantuml_bytes(uml_code, plantuml_jar_name="plantuml-1-2025-4.jar"):
    """Generate PlantUML diagram and return PNG bytes (async-safe)"""
    try:
        # Get script directory
        script_dir = os.path.dirname(os.path.abspath(__file__))
        plantuml_jar_path = os.path.join(script_dir, plantuml_jar_name)

        # Create a temporary file for UML code
        def _write_tempfile():
            with tempfile.NamedTemporaryFile(mode='w', suffix='.puml', delete=False) as temp_file:
                temp_file.write(uml_code)
                return temp_file.name

        temp_puml_path = await asyncio.to_thread(_write_tempfile)

        # Run PlantUML and output to stdout as PNG bytes
        cmd = [
            'java', '-jar', plantuml_jar_path,
            '-tpng',  # PNG output
            '-pipe'   # Output to stdout
        ]

        result = await asyncio.to_thread(
            subprocess.run, cmd, input=open(temp_puml_path, "rb").read(),
            capture_output=True, timeout=30
        )

        # Clean up temp file
        await asyncio.to_thread(os.unlink, temp_puml_path)

        if result.returncode == 0:
            return result.stdout  # PNG bytes
        else:
            print(f"PlantUML error: {result.stderr.decode()}")
            return None

    except FileNotFoundError:
        print("Java or plantuml.jar not found. Please install Java and download plantuml.jar")
        return None
    except Exception as e:
        print(f"Error: {e}")
        return None



import asyncio

if __name__ == "__main__":
    uml_code = """
@startuml
' Actors
actor User
actor "Food Delivery Service" as FoodDeliveryService

' System boundary for the Food Diary and Recommendation System
rectangle "Food Diary & Recommendation System" {

    ' Use cases related to food diary and meal tracking
    usecase "Log Meal" as UC_LogMeal
    usecase "Track Dietary Habits" as UC_TrackDiet
    usecase "Receive Personalized Insights" as UC_PersonalizedInsights
    usecase "Import Meal Data from Delivery Services" as UC_ImportMealData

    ' Use cases related to recommendations
    usecase "Get Personalized Meal Recommendations" as UC_GetMealRec
    usecase "Get Restaurant Recommendations" as UC_GetRestRec

    ' Community and social features
    usecase "Share Reviews" as UC_ShareReviews
    usecase "Interact with Food Community" as UC_InteractCommunity
    usecase "Participate in Discussions" as UC_ParticipateDiscussions

    ' Food ordering and integration features
    usecase "Order Food via Delivery Service" as UC_OrderFood
}

' Associations between actors and use cases
User --> UC_LogMeal
User --> UC_TrackDiet
User --> UC_PersonalizedInsights
User --> UC_ImportMealData
User --> UC_GetMealRec
User --> UC_GetRestRec
User --> UC_ShareReviews
User --> UC_InteractCommunity
User --> UC_ParticipateDiscussions
User --> UC_OrderFood

' Integration with external food delivery service
UC_ImportMealData <-- FoodDeliveryService
UC_OrderFood --> FoodDeliveryService

' Use case relationships for modularity
UC_LogMeal --> UC_TrackDiet : <>
UC_TrackDiet --> UC_PersonalizedInsights : <>
UC_ShareReviews --> UC_InteractCommunity : <>
UC_ParticipateDiscussions --> UC_InteractCommunity : <>

@enduml
"""

    async def main():
        png_bytes = await generate_plantuml_bytes(uml_code)
        if png_bytes:
            with open("diagram.png", "wb") as f:
                f.write(png_bytes)
            print("Diagram saved as diagram.png")
        else:
            print("Failed to generate diagram.")

    asyncio.run(main())



