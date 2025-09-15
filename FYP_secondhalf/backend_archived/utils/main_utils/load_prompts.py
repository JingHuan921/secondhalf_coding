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