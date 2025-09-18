# return {"errors": [f"Classification failed: {str(e)}"]}

# async def write_system_requirement_direct_api(state: ArtifactState) -> ArtifactState:
#     """
#     Write system requirements using direct OpenAI API calls
#     This completely bypasses LangChain to avoid any async compatibility issues
#     """
#     try:
#         print("DEBUG: write_system_requirement_direct_api started")
        
#         system_prompt = PROMPT_LIBRARY.get("write_system_req")
#         if not system_prompt:
#             raise ValueError("Missing 'write_system_req' prompt in prompt library.")
        
#         conversation_content = state.conversations[-1].content
#         print(f"DEBUG: Input content length: {len(conversation_content)}")
        
#         # Prepare the direct API request
#         api_key = os.environ.get('OPENAI_API_KEY')
#         if not api_key:
#             return {"errors": ["No OpenAI API key found"]}
        
#         # Create function schema for structured output
#         function_schema = {
#             "name": "create_system_requirements",
#             "description": "Create a list of system requirements",
#             "parameters": {
#                 "type": "object",
#                 "properties": {
#                     "requirements": {
#                         "type": "array",
#                         "items": {
#                             "type": "object",
#                             "properties": {
#                                 "id": {"type": "string", "description": "Unique identifier for the requirement"},
#                                 "title": {"type": "string", "description": "Short title of the requirement"},
#                                 "description": {"type": "string", "description": "Detailed description of the requirement"},
#                                 "priority": {"type": "string", "enum": ["high", "medium", "low"], "description": "Priority level"},
#                                 "category": {"type": "string", "description": "Category of the requirement"}
#                             },
#                             "required": ["id", "title", "description", "priority", "category"]
#                         }
#                     }
#                 },
#                 "required": ["requirements"]
#             }
#         }
        
#         # Prepare the API payload
#         payload = {
#             "model": "gpt-4o-mini",
#             "messages": [
#                 {"role": "system", "content": system_prompt},
#                 {"role": "user", "content": conversation_content}
#             ],
#             "functions": [function_schema],
#             "function_call": {"name": "create_system_requirements"},
#             "temperature": 0,
#             "timeout": 60
#         }
        
#         headers = {
#             "Authorization": f"Bearer {api_key}",
#             "Content-Type": "application/json"
#         }
        
#         print("DEBUG: Making direct API call to OpenAI...")
        
#         async with aiohttp.ClientSession() as session:
#             start = time.time()
            
#             try:
#                 async with session.post(
#                     "https://api.openai.com/v1/chat/completions",
#                     json=payload,
#                     headers=headers,
#                     timeout=aiohttp.ClientTimeout(total=60)
#                 ) as response:
#                     elapsed = time.time() - start
#                     print(f"DEBUG: API call completed in {elapsed:.2f}s")
                    
#                     if response.status == 200:
#                         data = await response.json()
#                         print("DEBUG: API call successful, parsing response...")
                        
#                         # Extract function call result
#                         if 'choices' in data and len(data['choices']) > 0:
#                             choice = data['choices'][0]
                            
#                             if 'message' in choice and 'function_call' in choice['message']:
#                                 function_call = choice['message']['function_call']
#                                 arguments_str = function_call['arguments']
                                
#                                 # Parse the function arguments
#                                 try:
#                                     function_result = json.loads(arguments_str)
#                                     print("DEBUG: Function call result parsed successfully")
                                    
#                                     # Convert to our expected format
#                                     requirements_data = function_result.get('requirements', [])
                                    
#                                     # Create a SystemRequirementsList-compatible object
#                                     response_content = {
#                                         "requirements": requirements_data
#                                     }
                                    
#                                     converted_text = json.dumps(response_content, indent=2)
                                    
#                                     print("DEBUG: Creating artifacts...")
                                    
#                                     # Create artifacts
#                                     artifact = create_artifact(
#                                         agent=AgentType.ANALYST,
#                                         artifact_type=ArtifactType.SYSTEM_REQ,
#                                         content=response_content,
#                                     )
                                    
#                                     conversation = create_conversation(
#                                         agent=AgentType.ANALYST,
#                                         artifact_id=artifact.id,
#                                         content=converted_text
#                                     )
                                    
#                                     print("DEBUG: write_system_requirement_direct_api completed successfully")
                                    
#                                     return {
#                                         "artifacts": [artifact],
#                                         "conversations": [conversation],
#                                     }
                                    
#                                 except json.JSONDecodeError as je:
#                                     print(f"ERROR: Failed to parse function arguments: {je}")
#                                     return {"errors": [f"Failed to parse API response: {str(je)}"]}
                            
#                             elif 'message' in choice and 'content' in choice['message']:
#                                 # Fallback: regular text response
#                                 content = choice['message']['content']
#                                 print("DEBUG: Got regular text response, attempting JSON parse...")
                                
#                                 try:
#                                     parsed_content = json.loads(content)
#                                     response_content = parsed_content
#                                     converted_text = content
#                                 except json.JSONDecodeError:
#                                     print("DEBUG: Could not parse as JSON, using raw text")
#                                     response_content = {"requirements": [], "raw_response": content}
#                                     converted_text = content
                                
#                                 # Create artifacts
#                                 artifact = create_artifact(
#                                     agent=AgentType.ANALYST,
#                                     artifact_type=ArtifactType.SYSTEM_REQ,
#                                     content=response_content,
#                                 )
                                
#                                 conversation = create_conversation(
#                                     agent=AgentType.ANALYST,
#                                     artifact_id=artifact.id,
#                                     content=converted_text
#                                 )
                                
#                                 return {
#                                     "artifacts": [artifact],
#                                     "conversations": [conversation],
#                                 }
                        
#                         return {"errors": ["Unexpected API response format"]}
                        
#                     else:
#                         error_text = await response.text()
#                         print(f"ERROR: API call failed with status {response.status}: {error_text[:200]}")
#                         return {"errors": [f"OpenAI API error {response.status}: {error_text[:200]}"]}
                        
#             except asyncio.TimeoutError:
#                 print("ERROR: Direct API call timed out")
#                 return {"errors": ["OpenAI API call timed out"]}
#             except Exception as api_e:
#                 print(f"ERROR: Direct API call failed: {api_e}")
#                 return {"errors": [f"Direct API call failed: {str(api_e)}"]}"""
# Fixed flow.py with comprehensive debugging and LLM async fixes
# Working @30 Aug: moved here cos I wanted to test state storing using sqlite async saver
# """

# from typing import Any, Dict, List, Union, Optional, Annotated
# import os
# import json
# import asyncio
# from operator import add
# import time
# import threading
# from concurrent.futures import ThreadPoolExecutor
# import aiohttp

# from backend.path_global_file import PROMPT_DIR_ANALYST
# from backend.utils.main_utils import (
#     load_prompts, generate_plantuml_local, extract_plantuml, pydantic_to_json_text
# )
# from backend.graph_logic.state import (
#     AgentType, ArtifactType, Artifact, Conversation, ArtifactState, StateManager,
#     create_artifact, create_conversation, add_artifacts, add_conversations, 
#      _get_latest_version, _increment_version, _create_versioned_artifact
# )
# from backend.artifact_model import RequirementsClassificationList, SystemRequirementsList, RequirementsModel, SoftwareRequirementSpecs

# from pydantic import BaseModel

# from langchain_core.tools import tool 
# from langgraph.graph import StateGraph, END
# from langchain_core.messages import HumanMessage, SystemMessage, AIMessage
# from langchain_core.prompts import ChatPromptTemplate
# from langgraph.prebuilt import ToolNode

# import os
# from dotenv import load_dotenv
# from langchain_openai import ChatOpenAI  # Direct import instead of init_chat_model
# from operator import add

# from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver

# # Load environment variables
# load_dotenv(override=True)

# if not os.environ.get("OPENAI_API_KEY"):
#     import getpass
#     os.environ["OPENAI_API_KEY"] = getpass.getpass("Enter your OpenAI API key: ")

# # Global variables
# shared_resources = {}
# graph = None

# # Load prompt library once
# prompt_path = PROMPT_DIR_ANALYST
# PROMPT_LIBRARY = load_prompts(prompt_path)

# # Fixed LLM initialization - using a model that supports structured outputs
# try:
#     llm = ChatOpenAI(
#         model="gpt-4o-mini",  # Supports structured outputs and is faster/cheaper
#         temperature=0,
#         timeout=60,  # Explicit timeout
#         max_retries=2,
#         openai_api_key=os.environ.get('OPENAI_API_KEY')
#     )
#     print(f"INFO: LLM initialized successfully: {type(llm)}")
# except Exception as e:
#     print(f"ERROR: Failed to initialize LLM: {e}")
#     llm = None

# # Diagnostic functions
# async def test_llm_connectivity():
#     """Test basic LLM connectivity outside of LangGraph context"""
#     if not llm:
#         return False, "LLM not initialized"
    
#     try:
#         print("DEBUG: Testing basic LLM connectivity...")
#         start = time.time()
#         response = await asyncio.wait_for(
#             llm.ainvoke([HumanMessage(content="Say 'OK'")]), 
#             timeout=15.0
#         )
#         elapsed = time.time() - start
#         print(f"DEBUG: LLM connectivity test successful in {elapsed:.2f}s: {response.content}")
#         return True, "Success"
#     except asyncio.TimeoutError:
#         print("ERROR: LLM connectivity test timed out")
#         return False, "Timeout"
#     except Exception as e:
#         print(f"ERROR: LLM connectivity test failed: {e}")
#         return False, str(e)

# async def test_openai_direct_api():
#     """Test direct OpenAI API call"""
#     try:
#         print("DEBUG: Testing direct OpenAI API...")
#         api_key = os.environ.get('OPENAI_API_KEY')
        
#         payload = {
#             "model": "gpt-3.5-turbo",
#             "messages": [{"role": "user", "content": "Say 'DIRECT_API_OK'"}],
#             "max_tokens": 10,
#             "temperature": 0
#         }
        
#         headers = {
#             "Authorization": f"Bearer {api_key}",
#             "Content-Type": "application/json"
#         }
        
#         async with aiohttp.ClientSession() as session:
#             start = time.time()
#             async with session.post(
#                 "https://api.openai.com/v1/chat/completions",
#                 json=payload,
#                 headers=headers,
#                 timeout=aiohttp.ClientTimeout(total=20)
#             ) as response:
#                 elapsed = time.time() - start
                
#                 if response.status == 200:
#                     data = await response.json()
#                     content = data['choices'][0]['message']['content']
#                     print(f"DEBUG: Direct API test successful in {elapsed:.2f}s: {content}")
#                     return True, content
#                 else:
#                     error_text = await response.text()
#                     print(f"ERROR: Direct API test failed {response.status}: {error_text[:200]}")
#                     return False, f"HTTP {response.status}"
                    
#     except Exception as e:
#         print(f"ERROR: Direct API test failed: {e}")
#         return False, str(e)

# def create_sync_llm():
#     """Create synchronous LLM for executor workaround"""
#     try:
#         sync_llm = ChatOpenAI(
#             model="gpt-3.5-turbo",
#             temperature=0,
#             timeout=60,
#             openai_api_key=os.environ.get('OPENAI_API_KEY')
#         )
#         return sync_llm
#     except Exception as e:
#         print(f"ERROR: Failed to create sync LLM: {e}")
#         return None

# # Node functions
# def process_user_input(state: ArtifactState) -> ArtifactState:
#     """
#     First node: Convert user input to conversation entry
#     This is the entry point that processes the user input from LangGraph Studio
#     """
#     try:
#         print("DEBUG: process_user_input started")
        
#         # Check if there's user input
#         if not state.human_request or state.human_request.strip() == "":
#             return {
#                 "errors": ["No user input provided"],
#             }
        
#         user_input = state.human_request.strip()
#         state.current_agent = AgentType.USER
        
#         # Create conversation entry for user input
#         user_conversation = create_conversation(
#             agent=AgentType.USER,
#             artifact_id=None,  # No artifact yet for user input
#             content=user_input,
#         )
        
#         print(f"DEBUG: process_user_input completed, input length: {len(user_input)}")
#         return {
#             "conversations": [user_conversation]
#         }
        
#     except Exception as e:
#         print(f"ERROR: process_user_input failed: {e}")
#         return {
#             "errors": [f"Failed to process user input: {str(e)}"]
#         }

# async def classify_user_requirements(state: ArtifactState) -> ArtifactState:
#     """Classify user requirements with improved error handling"""
#     try:
#         print("DEBUG: classify_user_requirements started")
        
#         # Test LLM connectivity first
#         connectivity_ok, connectivity_msg = await test_llm_connectivity()
#         if not connectivity_ok:
#             print(f"ERROR: LLM connectivity failed: {connectivity_msg}")
#             return {"errors": [f"LLM connectivity failed: {connectivity_msg}"]}
        
#         system_prompt = PROMPT_LIBRARY.get("classify_user_reqs")
#         if not system_prompt:
#             raise ValueError("Missing 'classify_user_reqs' prompt in prompt library.")
        
#         print("DEBUG: Attempting structured output for classification...")
#         llm_with_structured_output = llm.with_structured_output(
#             RequirementsClassificationList, 
#             method="function_calling"
#         )
        
#         start = time.time()
#         response = await asyncio.wait_for(
#             llm_with_structured_output.ainvoke([
#                 SystemMessage(content=system_prompt),
#                 HumanMessage(content=state.conversations[-1].content)
#             ]),
#             timeout=45.0
#         )
#         elapsed = time.time() - start
        
#         print(f"DEBUG: Classification successful in {elapsed:.2f}s")
#         converted_text = await pydantic_to_json_text(response)

#         # Create artifact using factory function
#         artifact = create_artifact(
#             agent=AgentType.ANALYST,
#             artifact_type=ArtifactType.REQ_CLASS,
#             content=response,  
#         )
        
#         # Create conversation entry
#         conversation = create_conversation(
#             agent=AgentType.ANALYST,
#             artifact_id=artifact.id,
#             content=converted_text
#         )
        
#         print("DEBUG: classify_user_requirements completed successfully")
#         return {
#             "artifacts": [artifact],  
#             "conversations": [conversation],  
#         }
        
#     except asyncio.TimeoutError:
#         print("ERROR: Classification timed out")
#         return {"errors": ["Classification request timed out"]}
#     except Exception as e:
#         print(f"ERROR: classify_user_requirements failed: {e}")
#         return {"errors": [f"Classification failed: {str(e)}"]}

# async def write_system_requirement_executor_only(state: ArtifactState) -> ArtifactState:
#     """
#     Write system requirements using thread executor to bypass async issues
#     This completely avoids LangChain's async methods which are hanging
#     """
#     try:
#         print("DEBUG: write_system_requirement_executor_only started")
        
#         system_prompt = PROMPT_LIBRARY.get("write_system_req")
#         if not system_prompt:
#             raise ValueError("Missing 'write_system_req' prompt in prompt library.")
        
#         conversation_content = state.conversations[-1].content
#         print(f"DEBUG: Input content length: {len(conversation_content)}")
        
#         print("DEBUG: Using thread executor strategy (bypassing async entirely)...")
        
#         def sync_llm_call():
#             """Synchronous LLM call that runs in executor thread"""
#             try:
#                 print("DEBUG: Creating sync LLM in executor thread...")
                
#                 # Create fresh sync LLM in executor thread
#                 sync_llm = ChatOpenAI(
#                     model="gpt-4o-mini",
#                     temperature=0,
#                     timeout=60,
#                     openai_api_key=os.environ.get('OPENAI_API_KEY')
#                 )
                
#                 print("DEBUG: Sync LLM created, attempting structured output...")
                
#                 # Try structured output first
#                 try:
#                     sync_structured_llm = sync_llm.with_structured_output(
#                         SystemRequirementsList,
#                         method="function_calling"
#                     )
                    
#                     messages = [
#                         SystemMessage(content=system_prompt),
#                         HumanMessage(content=conversation_content)
#                     ]
                    
#                     print("DEBUG: Calling sync invoke with structured output...")
#                     # Use synchronous invoke (not ainvoke)
#                     response = sync_structured_llm.invoke(messages)
#                     print("DEBUG: Structured sync invoke successful!")
#                     print("DEBUG: About to return from executor thread...")
                    
#                     result = {"type": "structured", "response": response}
#                     print("DEBUG: Result object created in executor thread")
#                     return result
                    
#                 except Exception as struct_e:
#                     print(f"DEBUG: Structured output failed in executor: {struct_e}")
#                     print("DEBUG: Falling back to regular sync invoke...")
                    
#                     # Fallback to regular response
#                     messages = [
#                         SystemMessage(content=system_prompt + "\n\nPlease respond in valid JSON format for SystemRequirementsList."),
#                         HumanMessage(content=conversation_content)
#                     ]
                    
#                     response = sync_llm.invoke(messages)
#                     print("DEBUG: Regular sync invoke successful!")
#                     print("DEBUG: About to return fallback from executor thread...")
                    
#                     result = {"type": "text", "response": response}
#                     print("DEBUG: Fallback result object created in executor thread")
#                     return result
                    
#             except Exception as e:
#                 print(f"ERROR: Sync LLM call failed: {e}")
#                 return {"type": "error", "error": str(e)}
        
#         print("DEBUG: Setting up thread executor...")
#         loop = asyncio.get_event_loop()
        
#         with ThreadPoolExecutor(max_workers=1) as executor:
#             print("DEBUG: Submitting sync_llm_call to executor...")
#             start = time.time()
            
#             try:
#                 print("DEBUG: About to await run_in_executor...")
#                 # This runs the synchronous LLM call in a separate thread
#                 result = await loop.run_in_executor(executor, sync_llm_call)
#                 print("DEBUG: run_in_executor returned successfully!")
                
#                 elapsed = time.time() - start
#                 print(f"DEBUG: Executor completed in {elapsed:.2f}s")
#                 print(f"DEBUG: Result type: {result.get('type', 'unknown')}")
                
#             except Exception as exec_e:
#                 print(f"ERROR: run_in_executor failed: {exec_e}")
#                 return {"errors": [f"Executor failed: {str(exec_e)}"]}
            
#             if result["type"] == "error":
#                 return {"errors": [f"Executor LLM call failed: {result['error']}"]}
            
#             print("DEBUG: Processing executor result...")
            
#             # Process the result
#             if result["type"] == "structured":
#                 print("DEBUG: Processing structured response...")
#                 response_content = result["response"]
#                 print("DEBUG: About to convert to JSON text...")
                
#                 try:
#                     converted_text = await pydantic_to_json_text(response_content)
#                     print("DEBUG: JSON conversion successful")
#                 except Exception as json_e:
#                     print(f"ERROR: JSON conversion failed: {json_e}")
#                     converted_text = str(response_content)
                    
#             else:
#                 print("DEBUG: Processing text response...")
#                 response_content = result["response"].content
#                 converted_text = response_content
                
#                 # Try to parse as JSON to convert to structured format
#                 try:
#                     import json
#                     parsed_json = json.loads(converted_text)
#                     print("DEBUG: Successfully parsed text response as JSON")
#                     response_content = parsed_json
#                 except json.JSONDecodeError:
#                     print("DEBUG: Could not parse as JSON, using raw text")
            
#             print("DEBUG: Creating artifacts...")
            
#             try:
#                 # Create artifacts
#                 artifact = create_artifact(
#                     agent=AgentType.ANALYST,
#                     artifact_type=ArtifactType.SYSTEM_REQ,
#                     content=response_content,
#                 )
#                 print("DEBUG: Artifact created successfully")
                
#                 conversation = create_conversation(
#                     agent=AgentType.ANALYST,
#                     artifact_id=artifact.id,
#                     content=converted_text
#                 )
#                 print("DEBUG: Conversation created successfully")
                
#             except Exception as artifact_e:
#                 print(f"ERROR: Artifact creation failed: {artifact_e}")
#                 return {"errors": [f"Artifact creation failed: {str(artifact_e)}"]}
            
#             print("DEBUG: write_system_requirement_executor_only completed successfully")
            
#             return {
#                 "artifacts": [artifact],
#                 "conversations": [conversation],
#             }
                
#     except Exception as e:
#         print(f"ERROR: write_system_requirement_executor_only failed: {e}")
#         import traceback
#         print(f"ERROR: Traceback: {traceback.format_exc()}")
#         return {"errors": [f"System requirement generation failed: {str(e)}"]}

# async def classify_user_requirements_executor(state: ArtifactState) -> ArtifactState:
#     """Classify user requirements using executor to bypass async issues"""
#     try:
#         print("DEBUG: classify_user_requirements_executor started")
        
#         system_prompt = PROMPT_LIBRARY.get("classify_user_reqs")
#         if not system_prompt:
#             raise ValueError("Missing 'classify_user_reqs' prompt in prompt library.")
        
#         conversation_content = state.conversations[-1].content
        
#         def sync_classify_call():
#             try:
#                 sync_llm = ChatOpenAI(
#                     model="gpt-4o-mini",
#                     temperature=0,
#                     timeout=60,
#                     openai_api_key=os.environ.get('OPENAI_API_KEY')
#                 )
                
#                 sync_structured_llm = sync_llm.with_structured_output(
#                     RequirementsClassificationList,
#                     method="function_calling"
#                 )
                
#                 messages = [
#                     SystemMessage(content=system_prompt),
#                     HumanMessage(content=conversation_content)
#                 ]
                
#                 response = sync_structured_llm.invoke(messages)
#                 return {"type": "structured", "response": response}
                
#             except Exception as e:
#                 return {"type": "error", "error": str(e)}
        
#         loop = asyncio.get_event_loop()
#         with ThreadPoolExecutor(max_workers=1) as executor:
#             start = time.time()
#             result = await loop.run_in_executor(executor, sync_classify_call)
#             elapsed = time.time() - start
            
#             print(f"DEBUG: Classification executor completed in {elapsed:.2f}s")
            
#             if result["type"] == "error":
#                 return {"errors": [f"Classification failed: {result['error']}"]}
            
#             response = result["response"]
#             converted_text = await pydantic_to_json_text(response)

#             # Create artifact using factory function
#             artifact = create_artifact(
#                 agent=AgentType.ANALYST,
#                 artifact_type=ArtifactType.REQ_CLASS,
#                 content=response,  
#             )
            
#             # Create conversation entry
#             conversation = create_conversation(
#                 agent=AgentType.ANALYST,
#                 artifact_id=artifact.id,
#                 content=converted_text
#             )
            
#             print("DEBUG: classify_user_requirements_executor completed successfully")
#             return {
#                 "artifacts": [artifact],  
#                 "conversations": [conversation],  
#             }
        
#     except Exception as e:
#         print(f"ERROR: classify_user_requirements_executor failed: {e}")
#         return {"errors": [f"Classification failed: {str(e)}"]}

# async def build_requirement_model_executor(state: ArtifactState) -> ArtifactState:
#     """Build requirement model using executor to bypass async issues"""
#     try:
#         print("DEBUG: build_requirement_model_executor started")
        
#         if not state.conversations:
#             return {"errors": ["No conversations available for processing"]}
        
#         system_prompt = PROMPT_LIBRARY.get("build_req_model")
#         if not system_prompt:
#             raise ValueError("Missing 'build_req_model' prompt in prompt library.")
        
#         conversation_content = state.conversations[-1].content
        
#         def sync_model_call():
#             try:
#                 sync_llm = ChatOpenAI(
#                     model="gpt-4o-mini",
#                     temperature=0,
#                     timeout=60,
#                     openai_api_key=os.environ.get('OPENAI_API_KEY')
#                 )
                
#                 messages = [
#                     SystemMessage(content=system_prompt),
#                     HumanMessage(content=conversation_content)
#                 ]
                
#                 response = sync_llm.invoke(messages)
#                 return {"type": "text", "response": response}
                
#             except Exception as e:
#                 return {"type": "error", "error": str(e)}
        
#         loop = asyncio.get_event_loop()
#         with ThreadPoolExecutor(max_workers=1) as executor:
#             start = time.time()
#             result = await loop.run_in_executor(executor, sync_model_call)
#             elapsed = time.time() - start
            
#             print(f"DEBUG: Model building executor completed in {elapsed:.2f}s")
            
#             if result["type"] == "error":
#                 return {"errors": [f"Model building failed: {result['error']}"]}
            
#             response = result["response"]
            
#             # Extract PlantUML code from the response
#             uml_chunk = None
#             diagram_generation_message = "No PlantUML code found in response."
            
#             if hasattr(response, 'content') and response.content:
#                 try:
#                     uml_chunk = extract_plantuml(response.content)
                    
#                     # Generate the diagram using the tool
#                     diagram_result = await generate_use_case_diagram(uml_code=uml_chunk)
#                     diagram_generation_message = diagram_result
                    
#                 except ValueError:
#                     uml_chunk = None
#                     diagram_generation_message = "No PlantUML code found in the LLM response."
#                 except Exception as e:
#                     diagram_generation_message = f"Error generating diagram: {str(e)}"
            
#             # Create final response
#             final_response_content = uml_chunk if uml_chunk else (response.content if hasattr(response, 'content') else str(response))
            
#             # Create artifact using factory function
#             artifact = create_artifact(
#                 agent=AgentType.ANALYST,
#                 artifact_type=ArtifactType.REQ_MODEL,
#                 content=final_response_content,  
#             )
            
#             # Create conversation entry
#             conversation = create_conversation(
#                 agent=AgentType.ANALYST,
#                 artifact_id=artifact.id,
#                 content=final_response_content,
#             )

#             print("DEBUG: build_requirement_model_executor completed successfully")
#             return {
#                 "artifacts": [artifact],  
#                 "conversations": [conversation],  
#             }
        
#     except Exception as e:
#         print(f"ERROR: build_requirement_model_executor failed: {e}")
#         return {"errors": [f"Requirement model generation failed: {str(e)}"]}

# async def write_system_requirement_with_fallback(state: ArtifactState) -> ArtifactState:
#     """
#     Write system requirements with multiple fallback strategies
#     """
#     try:
#         print("DEBUG: write_system_requirement_with_fallback started")
        
#         system_prompt = PROMPT_LIBRARY.get("write_system_req")
#         if not system_prompt:
#             raise ValueError("Missing 'write_system_req' prompt in prompt library.")
        
#         conversation_content = state.conversations[-1].content
#         print(f"DEBUG: Input content length: {len(conversation_content)}")
        
#         # Strategy 0: Test basic LLM connectivity first
#         print("DEBUG: Strategy 0 - Testing basic LLM connectivity...")
#         try:
#             print("DEBUG: About to test basic ainvoke...")
#             basic_test = await asyncio.wait_for(
#                 llm.ainvoke([HumanMessage(content="Say 'TEST_OK'")]),
#                 timeout=5.0
#             )
#             print(f"DEBUG: Basic test successful: {basic_test.content}")
#         except asyncio.TimeoutError:
#             print("ERROR: Basic LLM test timed out - definitely an async issue")
#             # Skip to executor strategy immediately
#             print("DEBUG: Skipping to Strategy 3 - Thread executor...")
            
#             def sync_llm_call():
#                 try:
#                     # Create fresh sync LLM in executor thread
#                     sync_llm = ChatOpenAI(
#                         model="gpt-4o-mini",
#                         temperature=0,
#                         timeout=60,
#                         openai_api_key=os.environ.get('OPENAI_API_KEY')
#                     )
                    
#                     # Try structured output first
#                     try:
#                         sync_structured_llm = sync_llm.with_structured_output(
#                             SystemRequirementsList,
#                             method="function_calling"
#                         )
                        
#                         messages = [
#                             SystemMessage(content=system_prompt),
#                             HumanMessage(content=conversation_content)
#                         ]
                        
#                         # Use synchronous invoke
#                         response = sync_structured_llm.invoke(messages)
#                         return {"type": "structured", "response": response}
                        
#                     except Exception as struct_e:
#                         print(f"DEBUG: Structured output failed in executor: {struct_e}")
                        
#                         # Fallback to regular response
#                         messages = [
#                             SystemMessage(content=system_prompt + "\n\nRespond in valid JSON format."),
#                             HumanMessage(content=conversation_content)
#                         ]
                        
#                         response = sync_llm.invoke(messages)
#                         return {"type": "text", "response": response}
                        
#                 except Exception as e:
#                     return {"type": "error", "error": str(e)}
            
#             try:
#                 loop = asyncio.get_event_loop()
#                 with ThreadPoolExecutor(max_workers=1) as executor:
#                     start = time.time()
#                     result = await loop.run_in_executor(executor, sync_llm_call)
#                     elapsed = time.time() - start
                    
#                     print(f"DEBUG: Executor strategy completed in {elapsed:.2f}s")
                    
#                     if result["type"] == "error":
#                         return {"errors": [f"Executor strategy failed: {result['error']}"]}
                    
#                     # Process the result
#                     if result["type"] == "structured":
#                         response_content = result["response"]
#                         converted_text = await pydantic_to_json_text(response_content)
#                     else:
#                         response_content = result["response"].content
#                         converted_text = response_content
                    
#                     # Create artifacts
#                     artifact = create_artifact(
#                         agent=AgentType.ANALYST,
#                         artifact_type=ArtifactType.SYSTEM_REQ,
#                         content=response_content,
#                     )
                    
#                     conversation = create_conversation(
#                         agent=AgentType.ANALYST,
#                         artifact_id=artifact.id,
#                         content=converted_text
#                     )
                    
#                     return {
#                         "artifacts": [artifact],
#                         "conversations": [conversation],
#                     }
                    
#             except Exception as e:
#                 print(f"ERROR: Executor strategy failed: {e}")
#                 return {"errors": [f"Executor strategy failed: {str(e)}"]}

#         except Exception as e:
#             print(f"ERROR: Basic LLM test failed: {e}")
#             return {"errors": [f"Basic LLM connectivity failed: {str(e)}"]}
        
#         # Strategy 1: Try normal async approach with more debugging
#         print("DEBUG: Attempting Strategy 1 - Normal async LLM call...")
#         try:
#             print("DEBUG: Creating structured output LLM...")
#             llm_with_structured_output = llm.with_structured_output(
#                 SystemRequirementsList, 
#                 method="function_calling"
#             )
#             print("DEBUG: Structured LLM created successfully")
            
#             messages = [
#                 SystemMessage(content=system_prompt),
#                 HumanMessage(content=conversation_content)
#             ]
#             print("DEBUG: Messages prepared, about to call ainvoke...")
            
#             # Add a much shorter timeout to fail fast
#             start = time.time()
#             print("DEBUG: Calling asyncio.wait_for with 10s timeout...")
            
#             response = await asyncio.wait_for(
#                 llm_with_structured_output.ainvoke(messages),
#                 timeout=10.0  # Reduced timeout to fail fast
#             )
#             elapsed = time.time() - start
            
#             print(f"DEBUG: Strategy 1 successful in {elapsed:.2f}s")
#             converted_text = await pydantic_to_json_text(response)
            
#             # Create artifacts
#             artifact = create_artifact(
#                 agent=AgentType.ANALYST,
#                 artifact_type=ArtifactType.SYSTEM_REQ,
#                 content=response,
#             )
            
#             conversation = create_conversation(
#                 agent=AgentType.ANALYST,
#                 artifact_id=artifact.id,
#                 content=converted_text
#             )
            
#             return {
#                 "artifacts": [artifact],
#                 "conversations": [conversation],
#             }
            
#         except asyncio.TimeoutError:
#             print("DEBUG: Strategy 1 timed out after 10s, trying Strategy 2...")
#         except Exception as e:
#             print(f"DEBUG: Strategy 1 failed with exception: {e}, trying Strategy 2...")
        
#         # Strategy 2: Try without structured output
#         print("DEBUG: Attempting Strategy 2 - Without structured output...")
#         try:
#             messages = [
#                 SystemMessage(content=system_prompt + "\n\nPlease respond in valid JSON format."),
#                 HumanMessage(content=conversation_content)
#             ]
            
#             start = time.time()
#             response = await asyncio.wait_for(
#                 llm.ainvoke(messages),
#                 timeout=30.0
#             )
#             elapsed = time.time() - start
            
#             print(f"DEBUG: Strategy 2 successful in {elapsed:.2f}s")
            
#             # Try to parse as JSON manually
#             try:
#                 import json
#                 parsed_response = json.loads(response.content)
#                 print("DEBUG: JSON parsing successful")
                
#                 # Create artifacts with parsed content
#                 artifact = create_artifact(
#                     agent=AgentType.ANALYST,
#                     artifact_type=ArtifactType.SYSTEM_REQ,
#                     content=parsed_response,
#                 )
                
#                 conversation = create_conversation(
#                     agent=AgentType.ANALYST,
#                     artifact_id=artifact.id,
#                     content=response.content
#                 )
                
#                 return {
#                     "artifacts": [artifact],
#                     "conversations": [conversation],
#                 }
                
#             except json.JSONDecodeError:
#                 print("DEBUG: JSON parsing failed, using raw response")
#                 # Use raw response
#                 artifact = create_artifact(
#                     agent=AgentType.ANALYST,
#                     artifact_type=ArtifactType.SYSTEM_REQ,
#                     content=response.content,
#                 )
                
#                 conversation = create_conversation(
#                     agent=AgentType.ANALYST,
#                     artifact_id=artifact.id,
#                     content=response.content
#                 )
                
#                 return {
#                     "artifacts": [artifact],
#                     "conversations": [conversation],
#                 }
                
#         except asyncio.TimeoutError:
#             print("DEBUG: Strategy 2 timed out, trying Strategy 3...")
#         except Exception as e:
#             print(f"DEBUG: Strategy 2 failed: {e}, trying Strategy 3...")
        
#         # Strategy 3: Thread executor workaround
#         print("DEBUG: Attempting Strategy 3 - Thread executor workaround...")
#         try:
#             def sync_llm_call():
#                 sync_llm = create_sync_llm()
#                 if not sync_llm:
#                     raise Exception("Failed to create sync LLM")
                
#                 messages = [
#                     SystemMessage(content=system_prompt + "\n\nPlease respond in valid JSON format."),
#                     HumanMessage(content=conversation_content)
#                 ]
                
#                 # Use synchronous invoke
#                 response = sync_llm.invoke(messages)
#                 return response.content
            
#             loop = asyncio.get_event_loop()
#             with ThreadPoolExecutor(max_workers=1) as executor:
#                 start = time.time()
#                 result = await loop.run_in_executor(executor, sync_llm_call)
#                 elapsed = time.time() - start
                
#                 print(f"DEBUG: Strategy 3 successful in {elapsed:.2f}s")
                
#                 # Create artifacts with executor result
#                 artifact = create_artifact(
#                     agent=AgentType.ANALYST,
#                     artifact_type=ArtifactType.SYSTEM_REQ,
#                     content=result,
#                 )
                
#                 conversation = create_conversation(
#                     agent=AgentType.ANALYST,
#                     artifact_id=artifact.id,
#                     content=result
#                 )
                
#                 return {
#                     "artifacts": [artifact],
#                     "conversations": [conversation],
#                 }
                
#         except Exception as e:
#             print(f"DEBUG: Strategy 3 failed: {e}")
        
#         # All strategies failed - this shouldn't happen with executor fallback
#         print("ERROR: All strategies failed")
#         return {"errors": ["All LLM call strategies failed"]}
        
#     except Exception as e:
#         print(f"ERROR: write_system_requirement_with_fallback crashed: {e}")
#         import traceback
#         print(f"ERROR: Traceback: {traceback.format_exc()}")
#         return {"errors": [f"System requirement generation failed: {str(e)}"]}

# async def build_requirement_model(state: ArtifactState) -> ArtifactState:
#     """Build requirement model with improved error handling"""
#     print("DEBUG: build_requirement_model function started")
    
#     if not state.conversations:
#         print("ERROR: No conversations found in state!")
#         return {"errors": ["No conversations available for processing"]}
    
#     try:
#         system_prompt = PROMPT_LIBRARY.get("build_req_model")
#         if not system_prompt:
#             raise ValueError("Missing 'build_req_model' prompt in prompt library.")
        
#         print("DEBUG: Invoking LLM for requirement model generation")
        
#         # Use the same fallback strategy as write_system_requirement
#         start = time.time()
#         response = await asyncio.wait_for(
#             llm.ainvoke([
#                 SystemMessage(content=system_prompt),
#                 HumanMessage(content=state.conversations[-1].content)
#             ]),
#             timeout=45.0
#         )
#         elapsed = time.time() - start
        
#         print(f"DEBUG: LLM response received successfully in {elapsed:.2f}s")
        
#         # Extract PlantUML code from the response
#         uml_chunk = None
#         diagram_generation_message = "No PlantUML code found in response."
        
#         if hasattr(response, 'content') and response.content:
#             print("DEBUG: LLM response has content, attempting UML extraction")
#             try:
#                 uml_chunk = extract_plantuml(response.content)
#                 print(f"DEBUG: UML extraction successful, chunk length: {len(uml_chunk)}")
                
#                 # Generate the diagram using the tool
#                 print("DEBUG: Attempting to generate use case diagram")
#                 diagram_result = await generate_use_case_diagram(uml_code=uml_chunk)
#                 diagram_generation_message = diagram_result
#                 print(f"DEBUG: Diagram generation completed: {diagram_generation_message}")
                
#             except ValueError as ve:
#                 print(f"DEBUG: ValueError during UML extraction: {ve}")
#                 uml_chunk = None
#                 diagram_generation_message = "No PlantUML code found in the LLM response."
#             except Exception as e:
#                 print(f"DEBUG: Exception during UML processing: {str(e)}")
#                 diagram_generation_message = f"Error generating diagram: {str(e)}"
        
#         # Create final response
#         final_response_content = uml_chunk if uml_chunk else (response.content if hasattr(response, 'content') else str(response))
        
#         # Create artifact using factory function
#         artifact = create_artifact(
#             agent=AgentType.ANALYST,
#             artifact_type=ArtifactType.REQ_MODEL,
#             content=final_response_content,  
#         )
        
#         # Create conversation entry
#         conversation = create_conversation(
#             agent=AgentType.ANALYST,
#             artifact_id=artifact.id,
#             content=final_response_content,
#         )

#         print("DEBUG: build_requirement_model function completed successfully")
#         return {
#             "artifacts": [artifact],  
#             "conversations": [conversation],  
#         }
    
#     except asyncio.TimeoutError:
#         print("ERROR: build_requirement_model timed out")
#         return {"errors": ["Requirement model generation timed out"]}
#     except Exception as e:
#         print(f"ERROR: Exception in build_requirement_model: {str(e)}")
#         import traceback
#         print(f"ERROR: Traceback: {traceback.format_exc()}")
#         return {"errors": [f"Requirement model generation failed: {str(e)}"]}

# async def generate_use_case_diagram(uml_code: str) -> str:
#     """Generate a use case diagram from PlantUML code"""
#     try:
#         print(f"DEBUG: generate_use_case_diagram started")
#         result = await generate_plantuml_local(uml_code=uml_code)
#         if result:
#             return f"Use case diagram generated successfully at: {result}"
#         else:
#             return f"Failed to generate use case diagram. Check PlantUML installation and code syntax."
        
#     except Exception as e:
#         return f"Error generating diagram: {str(e)}"

# async def write_req_specs(state: ArtifactState) -> ArtifactState:
#     """Write requirement specs with improved error handling"""
#     try:
#         print("DEBUG: write_req_specs started")
        
#         oel_input = """
#         1. Device Compatibility
#         Must support smartphones (iOS and Android) and optionally tablets.
#         Minimum device specifications: e.g., Android 8.0+ or iOS 14+.
#         Support both portrait and landscape orientations.
#         2. Operating System
#         Android devices: Android 8.0 and above.
#         iOS devices: iOS 14 and above.
#         Ensure compatibility with upcoming OS updates for at least 2 years.
#         3. Network Requirements
#         Must work on Wi-Fi and mobile data (3G/4G/5G).
#         Minimum bandwidth requirement for loading menus and images.
#         Offline mode: Allow browsing of previously loaded menus when offline.
#         4. Backend and APIs
#         App connects to a backend server via RESTful APIs or GraphQL.
#         Requires secure HTTPS connections.
#         Supports load balancing for at least 10,000 simultaneous users.
#         5. Browser Requirements (if web-based)
#         Support latest versions of Chrome, Safari, Firefox, and Edge.
#         Graceful degradation for unsupported browsers.
#         6. Storage and Memory
#         Local caching for offline use and performance optimization.
#         Minimum RAM usage constraints for smooth operation.
#         """

#         # manually input OEL first
#         oel_artifact = create_artifact(
#             agent=AgentType.DEPLOYER,
#             artifact_type=ArtifactType.OP_ENV_LIST,
#             content=oel_input,  
#         )

#         # extract latest versions of OEL, SRL and RM
#         latest_system_req = StateManager.get_latest_artifact_by_type(state, ArtifactType.SYSTEM_REQ)
#         latest_req_model = StateManager.get_latest_artifact_by_type(state, ArtifactType.REQ_MODEL)

#         system_req_content = await pydantic_to_json_text(latest_system_req.content)
#         req_model_content = latest_req_model.content
#         op_env_list_content = oel_artifact.content

#         system_req_id = latest_system_req.id
#         req_model_id = latest_req_model.id
#         op_env_list_id = oel_artifact.id

#         system_prompt = PROMPT_LIBRARY.get("write_req_specs")
#         if not system_prompt:
#             raise ValueError("Missing 'write_req_specs' prompt in prompt library.")
            
#         prompt_input = system_prompt.format(
#             system_req_content=system_req_content, 
#             req_model_content=req_model_content, 
#             op_env_list_content=op_env_list_content, 
#             system_req_id=system_req_id, 
#             req_model_id=req_model_id, 
#             op_env_list_id=op_env_list_id
#         )

#         llm_with_structured_output = llm.with_structured_output(
#             SoftwareRequirementSpecs, 
#             method="function_calling"
#         )
        
#         start = time.time()
#         response = await asyncio.wait_for(
#             llm_with_structured_output.ainvoke([
#                 SystemMessage(content=prompt_input),
#                 HumanMessage(content=state.conversations[-1].content)
#             ]),
#             timeout=60.0
#         )
#         elapsed = time.time() - start
        
#         print(f"DEBUG: write_req_specs completed in {elapsed:.2f}s")
        
#         converted_text = await pydantic_to_json_text(response)

#         # Create artifact using factory function
#         artifact = create_artifact(
#             agent=AgentType.ARCHIVIST,
#             artifact_type=ArtifactType.SW_REQ_SPECS,
#             content=response,  
#         )
        
#         # Create conversation entry
#         conversation = create_conversation(
#             agent=AgentType.ARCHIVIST,
#             artifact_id=artifact.id,
#             content=converted_text,
#         )
        
#         return {
#             "artifacts": [artifact],  
#             "conversations": [conversation],  
#         }
        
#     except asyncio.TimeoutError:
#         print("ERROR: write_req_specs timed out")
#         return {"errors": ["Requirements specification generation timed out"]}
#     except Exception as e:
#         print(f"ERROR: write_req_specs failed: {e}")
#         return {"errors": [f"Requirements specification failed: {str(e)}"]}

# async def verdict_to_revise_SRS(state: ArtifactState) -> str: 
#     """Determine if SRS needs revision"""
#     print("DEBUG: running verdict_to_revise_SRS routing function")
    
#     latest_val_report = StateManager.get_latest_artifact_by_type(state, ArtifactType.VAL_REPORT)    
#     if not latest_val_report: 
#         print("DEBUG: No validation report found, returning True")
#         return True
#     else:
#         try: 
#             val_report_content = latest_val_report.content 
#             val_report_id = latest_val_report.id
#             latest_srs = StateManager.get_latest_artifact_by_type(state, ArtifactType.SW_REQ_SPECS)    
#             srs_content = latest_srs.content
#             srs_id = latest_srs.id

#             system_prompt = PROMPT_LIBRARY.get("write_req_specs_with_val_rep")
#             if not system_prompt: 
#                 raise ValueError("Missing 'write_req_specs_with_val_rep' prompt in prompt library")
            
#             prompt_input = system_prompt.format(
#                 val_report_content=val_report_content, 
#                 srs_content=srs_content, 
#                 srs_id=srs_id, 
#                 val_report_id=val_report_id
#             )
            
#             response = await asyncio.wait_for(
#                 llm.ainvoke([
#                     SystemMessage(content=prompt_input), 
#                     HumanMessage(content=state.conversations[-1].content)
#                 ]),
#                 timeout=30.0
#             )

#             response_text = response.content.strip().upper()
#             if response_text == "YES": 
#                 print("DEBUG: Verdict: True (needs revision)")
#                 return True
#             elif response_text == "NO": 
#                 print("DEBUG: Verdict: False (no revision needed)")
#                 return False 
#             else: 
#                 print(f"WARNING: Unexpected LLM response: {response_text}, defaulting to False")
#                 return False
                
#         except Exception as e: 
#             print(f"ERROR: Error in verdict_to_revise_SRS: {e}")
#             return False  # Default to not revising on error

# async def revise_req_specs(state: ArtifactState) -> ArtifactState: 
#     """Revise requirement specifications"""
#     try:
#         print("DEBUG: revise_req_specs started")
        
#         latest_val_report = StateManager.get_latest_artifact_by_type(state, ArtifactType.VAL_REPORT)    
#         if not latest_val_report: 
#             return {"errors": ["No validation report found for revision"]}

#         val_report_content = latest_val_report.content 
#         val_report_id = latest_val_report.id
#         latest_srs = StateManager.get_latest_artifact_by_type(state, ArtifactType.SW_REQ_SPECS)    
#         srs_content = latest_srs.content
#         srs_id = latest_srs.id

#         system_prompt = PROMPT_LIBRARY.get("write_req_specs_with_val_rep")
#         if not system_prompt: 
#             raise ValueError("Missing 'write_req_specs_with_val_rep' prompt in prompt library")

#         prompt_input = system_prompt.format(
#             val_report_content=val_report_content, 
#             srs_content=srs_content, 
#             srs_id=srs_id, 
#             val_report_id=val_report_id
#         )

#         llm_with_structured_output = llm.with_structured_output(
#             SoftwareRequirementSpecs, 
#             method="function_calling"
#         )
        
#         start = time.time()
#         response = await asyncio.wait_for(
#             llm_with_structured_output.ainvoke([
#                 SystemMessage(content=prompt_input), 
#                 HumanMessage(content=state.conversations[-1].content)
#             ]),
#             timeout=60.0
#         )
#         elapsed = time.time() - start
        
#         print(f"DEBUG: revise_req_specs completed in {elapsed:.2f}s")

#         converted_text = await pydantic_to_json_text(response) 

#         artifact = create_artifact(
#             agent=AgentType.ARCHIVIST, 
#             artifact_type=ArtifactType.SW_REQ_SPECS, 
#             content=response,
#         )

#         conversation = create_conversation(
#             agent=AgentType.ARCHIVIST, 
#             artifact_id=artifact.id, 
#             content=converted_text,
#         )
        
#         return {
#             "artifacts": [artifact], 
#             "conversations": [conversation],
#         }
        
#     except asyncio.TimeoutError:
#         print("ERROR: revise_req_specs timed out")
#         return {"errors": ["Requirements revision timed out"]}
#     except Exception as e: 
#         print(f"ERROR: revise_req_specs failed: {e}")
#         return {"errors": [f"Requirements revision failed: {str(e)}"]}

# async def setup_state_graph(checkpointer: AsyncSqliteSaver):
#     """Setup the state graph with improved error handling"""
#     print("DEBUG: Setting up state graph...")
    
#     # Test LLM before building graph
#     if llm:
#         connectivity_ok, msg = await test_llm_connectivity()
#         if connectivity_ok:
#             print("INFO: LLM connectivity verified")
#         else:
#             print(f"WARNING: LLM connectivity issue: {msg}")
    
#     # Define a new graph
#     workflow = StateGraph(ArtifactState)
    
#     # Add nodes - using direct API versions to bypass LangChain entirely
#     workflow.add_node("process_user_input", process_user_input)
#     workflow.add_node("classify_user_requirements", classify_user_requirements_direct_api)
#     workflow.add_node("write_system_requirement_direct_api", write_system_requirement_direct_api)
#     workflow.add_node("build_requirement_model", build_requirement_model_executor)
#     workflow.add_node("write_req_specs", write_req_specs)
#     workflow.add_node("verdict_to_revise_SRS", verdict_to_revise_SRS)
#     workflow.add_node("revise_req_specs", revise_req_specs)

#     # Set the entrypoint
#     workflow.set_entry_point("process_user_input")
    
#     # Add edges
#     workflow.add_edge("process_user_input", "classify_user_requirements")
#     workflow.add_edge("classify_user_requirements", "write_system_requirement_direct_api")
#     workflow.add_edge("write_system_requirement_direct_api", "build_requirement_model")
#     workflow.add_edge("build_requirement_model", "write_req_specs")
#     workflow.add_conditional_edges(
#         "write_req_specs", 
#         verdict_to_revise_SRS, 
#         {True: "revise_req_specs", False: END}
#     )
#     workflow.add_edge("revise_req_specs", END)

#     # Compile graph
#     graph = workflow.compile(checkpointer=checkpointer)
#     shared_resources["graph"] = graph

#     print("Application startup: Resources initialized.")
#     return graph