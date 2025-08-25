import os
import tempfile
import subprocess
import time
from parse_uml import uml_portion

def generate_plantuml_local(plantuml_jar_path="plantuml-1-2025-4.jar", uml_code=uml_portion):
    """Generate PlantUML diagram using local PlantUML installation"""
    try:
        # Get the parent directory (one level up from where the Python script is located)
        script_dir = os.path.dirname(os.path.abspath(__file__))
        parent_dir = os.path.dirname(script_dir)
        
        # Create output directory in parent folder
        output_dir = os.path.join(parent_dir, "output")
        os.makedirs(output_dir, exist_ok=True)  # Creates directory if it doesn't exist, does nothing if it exists
        
        # Generate timestamp and filename
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        output_file = os.path.join(output_dir, f"diagram_{timestamp}.png")
        
        # Create a temporary file for the UML code
        with tempfile.NamedTemporaryFile(mode='w', suffix='.puml', delete=False) as temp_file:
            temp_file.write(uml_code)
            temp_puml_path = temp_file.name
        
        # Run PlantUML - output to script directory
        cmd = [
            'java', '-jar', plantuml_jar_path,
            '-tpng',  # Output format: PNG
            '-o', output_dir,  # Output directory (output folder in parent directory)
            temp_puml_path
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        
        if result.returncode == 0:
            # PlantUML generates file with same name as temp file but .png extension
            base_name = os.path.splitext(os.path.basename(temp_puml_path))[0]
            generated_file = os.path.join(output_dir, f"{base_name}.png")
            
            if os.path.exists(generated_file):
                # Rename to our desired timestamped filename
                os.rename(generated_file, output_file)
                print(f"PlantUML diagram generated successfully: {output_file}")
                
                # Clean up temp file
                os.unlink(temp_puml_path)
                return output_file
            else:
                print(f"Expected output file not found: {generated_file}")
                
        else:
            print(f"PlantUML error: {result.stderr}")
            
        # Clean up temp file in case of error
        if os.path.exists(temp_puml_path):
            os.unlink(temp_puml_path)
        return None
        
    except FileNotFoundError:
        print("Java or plantuml.jar not found. Please install Java and download plantuml.jar")
        return None
    except Exception as e:
        print(f"Error: {e}")
        return None
