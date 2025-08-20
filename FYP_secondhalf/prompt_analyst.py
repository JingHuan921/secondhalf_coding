{"name": "ClassifyUserReqs", 
 "template": "You are an expert requirements analyst. You are given a list of raw user requirements collected from interviews.\n\n"
            "Your task is to categorize each requirement into **functional** or **non-functional**, and assign a **priority level** "
            "(`high`, `medium`, or `low`). Use semantic cues, context, and known classification heuristics to guide your decisions.\n\n"
            "Respond in JSON format like this:\n"
            "[\n"
            "  {\"requirement\": \"<text>\", \"type\": \"functional\", \"priority\": \"high\"},\n"
            "  {\"requirement\": \"<text>\", \"type\": \"non-functional\", \"priority\": \"medium\"}\n"
            "]"
            }
{"name": "WriteSystemReqs",
 "template": "You are tasked with writing a System Requirements List (SRL) based on the previously classified and prioritized user requirements.\n\n"
            "Transform these user-oriented statements into structured, implementable system-level requirements using formal, testable language.\n\n"
            "Each requirement should be clear, concise, and verifiable.\n\n"
            "Respond in this format:\n"
            "[\n"
            "  {\"id\": \"SR-001\", \"requirement\": \"The system shall...\"},\n"
            "  {\"id\": \"SR-002\", \"requirement\": \"The system shall...\"}\n"
            "]"
            }
{"name": "BuildReqModel", 
 "template": "You are now constructing a Requirements Model (RM) based on the structured System Requirements List (SRL).\n\n"
            "Identify the key requirement entities (e.g., users, system components, actions) and their relationships. "
            "Use template-guided modeling techniques to define dependencies, hierarchies, or associations between entities.\n\n"
            "Represent your output in a JSON model format:\n"
            "{\n"
            "  \"entities\": [\"User\", \"LoginModule\", \"AuthenticationService\"],\n"
            "  \"relationships\": [\n"
            "    {\"from\": \"User\", \"to\": \"LoginModule\", \"type\": \"interacts_with\"},\n"
            "    {\"from\": \"LoginModule\", \"to\": \"AuthenticationService\", \"type\": \"uses\"}\n"
            "  ]\n"
            "}"
            }
