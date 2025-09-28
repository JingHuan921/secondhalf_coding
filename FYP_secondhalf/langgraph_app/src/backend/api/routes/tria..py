elif run_data["type"] == "artifact_feedback":
        event_type = "resume_artifact_feedback"
        artifact_id = run_data.get("artifact_id")
        artifact_action = run_data.get("artifact_action")
        artifact_feedback = run_data.get("artifact_feedback")
        
        print(f"DEBUG: Processing artifact feedback: {artifact_action} for {artifact_id}")
        
        if artifact_action == "accept":
            print(f"DEBUG: Artifact {artifact_id} accepted, continuing workflow")
            
            # Send acceptance confirmation to frontend
            acceptance_payload = json.dumps({
                "chat_type": "conversation",
                "content": f"✅ Artifact {artifact_id} has been accepted. Continuing with workflow...",
                "node": "artifact_feedback_processor",
                "agent": "System",
                "artifact_id": artifact_id,
                "timestamp": datetime.now(timezone.utc).isoformat()
            })
            yield acceptance_payload
            
            # Clear ALL feedback-related state and continue workflow
            await graph.aupdate_state(config, {
                "paused_for_feedback": False,
                "artifact_feedback_id": None,
                "artifact_feedback_action": None,
                "artifact_feedback_text": None
            })
            
            # Check if workflow should continue or finish
            final_status = await check_and_send_final_state()
            if final_status:
                yield final_status
            else:
                # Continue normal workflow execution
                print(f"DEBUG: Resuming normal workflow after artifact acceptance")
                # Don't return here - let the normal workflow continue
                input_state = None
            
        elif artifact_action == "feedback":
            print(f"DEBUG: Processing feedback for artifact {artifact_id}")
            
            try:
                current_state = await graph.aget_state(config)
                
                # Import and call your direct feedback processor
                from backend.graph_logic.flow import process_artifact_feedback_direct
                
                # Process feedback
                feedback_result = await process_artifact_feedback_direct({
                    **current_state.values,
                    'artifact_feedback_id': artifact_id,
                    'artifact_feedback_action': artifact_action,
                    'artifact_feedback_text': artifact_feedback
                })
                
                # Send conversation updates
                if "conversations" in feedback_result:
                    for conv in feedback_result["conversations"]:
                        conv_payload = json.dumps({
                            "chat_type": "conversation",
                            "content": conv.content,
                            "node": "artifact_feedback_processor",
                            "agent": conv.agent.value,
                            "artifact_id": conv.artifact_id,
                            "timestamp": conv.timestamp.isoformat()
                        })
                        yield conv_payload
                
                # Send revised artifacts and require feedback again
                if "artifacts" in feedback_result:
                    for art in feedback_result["artifacts"]:
                        print(f"DEBUG STREAM: Sending revised artifact {art.id}, version: {art.version}")
                        
                        # Serialize content
                        content_data = None
                        if art.content:
                            if hasattr(art.content, 'model_dump'):
                                content_data = art.content.model_dump()
                            else:
                                content_data = str(art.content)
                        
                        # Send the revised artifact
                        art_payload = json.dumps({
                            "chat_type": "artifact",
                            "artifact_id": art.id,
                            "artifact_type": art.content_type.value,
                            "agent": art.created_by.value if hasattr(art.created_by, 'value') else str(art.created_by),
                            "content": content_data,
                            "node": "artifact_feedback_processor",
                            "version": art.version,
                            "timestamp": art.timestamp.isoformat(),
                            "status": "completed"
                        })
                        yield art_payload
                        
                        # Immediately require feedback for the revised artifact
                        print(f"DEBUG: Requiring feedback for revised artifact {art.id}")
                        feedback_required_payload = json.dumps({
                            "chat_type": "artifact_feedback_required",
                            "status": "artifact_feedback_required", 
                            "pending_artifact_id": art.id,
                            "thread_id": thread_id,
                            "timestamp": datetime.now(timezone.utc).isoformat()
                        })
                        yield feedback_required_payload
                
                # Update graph state with results
                await graph.aupdate_state(config, feedback_result)
                
                # Keep paused for the next feedback cycle
                await graph.aupdate_state(config, {"paused_for_feedback": True})
                
            except Exception as e:
                print(f"ERROR: Failed to process artifact feedback: {str(e)}")
                error_payload = json.dumps({
                    "chat_type": "error",
                    "content": f"Failed to process feedback: {str(e)}",
                    "node": "artifact_feedback_processor",
                    "agent": "System"
                })
                yield error_payload
            
            # Exit and wait for next user action (accept or more feedback)
            return