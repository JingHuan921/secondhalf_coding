// src/routes.ts - COMPLETE FILE WITH ARTIFACT ACCEPT/FEEDBACK FUNCTIONALITY

// comes from event fetched from backend endpoint (start.py)
interface StreamMessage {
  thread_id?: string;
  chat_type?: "conversation" | "artifact" | "error" | "interrupt" | "routing_decision" | "artifact_feedback_required";
  content?: string;
  node?: string;
  agent?: string;
  artifact_id?: string;
  artifact_type?: string;
  version?: string;
  timestamp?: string;
  status?: "ready" | "user_feedback" | "finished" | "completed" | "waiting_for_user_input" | "artifact_feedback_required" | "connected" | "connection_test";
  error?: string;
  message?: string; // For interrupt messages
  next_node?: string; // For routing decisions
  pending_artifact_id?: string; // For artifact feedback
}

// for storing conversations from backend "conversation" in ArtifactState
interface ConversationMessage {
  role: "user" | "assistant";
  text: string;
  agent?: string;
  timestamp?: string;
  artifact_id?: string;
  isComplete: boolean;
}
// for storing artifacts from backend "artifact" in ArtifactState
interface ArtifactInfo {
  id: string;
  type: string;
  agent: string;
  version: string;
  timestamp: string;
  status: string;
  content?: any; // Add content field for the actual artifact data
}
// for frontend routing: message and controlling nodes routing (interrupt) and artifact feedback
interface ConversationState {
  currentMessage: string;
  isStreaming: boolean;
  chatType: "conversation" | "artifact" | null;
  threadId: string | null;
  requiresFeedback: boolean;
  isComplete: boolean;
  error: string | null;
  currentAgent?: string;
  currentNode?: string;
  artifacts: ArtifactInfo[];
  // Interrupt-related fields
  isInterrupted: boolean;
  interruptMessage?: string;
  availableChoices?: Array<{value: string, label: string}>;
  // Artifact feedback fields
  requiresArtifactFeedback: boolean;
  pendingFeedbackArtifactId?: string;
  // Array to store all messages
  messages: ConversationMessage[];
}

// Available routing choices
const ROUTING_CHOICES = [
  { value: 'classify_user_requirements', label: 'Classify User Requirements' },
  { value: 'write_system_requirement', label: 'Write System Requirement' },
  { value: 'build_requirement_model', label: 'Build Requirement Model' },
  { value: 'write_req_specs', label: 'Write Requirement Specs' },
  { value: 'revise_req_specs', label: 'Revise Requirement Specs' }, 
  { value: 'no', label: 'END Node' }, 
];

// Enhanced version of your sendUserPrompt function
async function sendUserPrompt(prompt: string, onStateUpdate: (state: ConversationState) => void) {
  try {
    console.log("Sending prompt:", prompt);
    
    // Step 1: Create a new stream
    const createRes = await fetch("http://localhost:8000/graph/stream/create", {
      method: "POST",
      headers: { 
        "Content-Type": "application/json",
        "Accept": "application/json"
      },
      body: JSON.stringify({
        thread_id: "",
        human_request: prompt,
      }),
    });

    console.log("Create response status:", createRes.status);
    console.log("Create response headers:", Object.fromEntries(createRes.headers.entries()));

    if (!createRes.ok) {
      let errorMessage = `Server error: ${createRes.status} ${createRes.statusText}`;
      
      try {
        const errorData = await createRes.text();
        console.error("Server error response:", errorData);
        errorMessage += `\nDetails: ${errorData}`;
      } catch (e) {
        console.error("Could not read error response");
      }

      throw new Error(errorMessage);
    }

    const createData = await createRes.json();
    console.log("Create response data:", createData);
    
    const threadId = createData.thread_id;

    if (!threadId) {
      throw new Error("No thread_id received from server");
    }

    console.log("Thread started:", threadId);

    // Initialize state
    const initialState: ConversationState = {
      currentMessage: "",
      isStreaming: true,
      chatType: null,
      threadId,
      requiresFeedback: false,
      isComplete: false,
      error: null,
      artifacts: [],
      isInterrupted: false,
      requiresArtifactFeedback: false,
      messages: [] // Initialize empty messages array
    };

    onStateUpdate(initialState);

    // Step 2: Start streaming from backend
    streamAssistantResponse(threadId, onStateUpdate);

  } catch (error) {
    console.error("Error in sendUserPrompt:", error);
    
    // Check if it's a CORS error
    if (error instanceof TypeError && error.message.includes('Failed to fetch')) {
      console.error("Likely CORS issue - check backend CORS configuration");
    }
    
    // Update state with error
    const errorState: ConversationState = {
      currentMessage: "",
      isStreaming: false,
      chatType: null,
      threadId: null,
      requiresFeedback: false,
      isComplete: false,
      error: error instanceof Error ? error.message : "Unknown error occurred",
      artifacts: [],
      isInterrupted: false,
      requiresArtifactFeedback: false,
      messages: []
    };

    onStateUpdate(errorState);
  }
}

// Modified streaming function that preserves existing state
function streamAssistantResponseWithState(
  threadId: string, 
  onStateUpdate: (state: ConversationState) => void,
  existingState?: ConversationState
) {
  //when running this, we will access a new run_config with the latest update (Note: frontend router maybe updating the state in here)
  const streamUrl = `http://localhost:8000/graph/stream/${threadId}`;
  console.log("Starting stream from:", streamUrl);
  console.log("=== STARTING SSE CONNECTION ===");
  console.log("Stream URL:", streamUrl);
  console.log("Thread ID:", threadId);
  
  // Test server connectivity first
  fetch(`http://localhost:8000/health`)
    .then(response => {
      console.log("Health check response:", response.status);
      return response.json();
    })
    .then(data => {
      console.log("Server health:", data);
    })
    .catch(error => {
      console.error("Server health check failed:", error);
    });


  const eventSource = new EventSource(streamUrl);

  // Use existing state if provided, otherwise create new state
  let currentState: ConversationState = existingState || {
    currentMessage: "",
    isStreaming: true,
    chatType: null,
    threadId,
    requiresFeedback: false,
    isComplete: false,
    error: null,
    artifacts: [],
    isInterrupted: false,
    requiresArtifactFeedback: false,
    messages: []
  };

  const updateState = (updates: Partial<ConversationState>) => {
    currentState = { ...currentState, ...updates };
    onStateUpdate(currentState);
  };

  const addMessage = (message: ConversationMessage) => {
    const newMessages = [...currentState.messages, message];
    updateState({
      messages: newMessages,
      currentMessage: message.text,
      currentAgent: message.agent
    });
  };

  const addArtifact = (artifact: ArtifactInfo) => {
    const newArtifacts = [...currentState.artifacts, artifact];
    updateState({
      artifacts: newArtifacts
    });
  };


// Connection state tracking
  let connectionAttempts = 0;
  const maxRetries = 3;
  let retryTimeout: NodeJS.Timeout;

  const attemptReconnection = () => {
    if (connectionAttempts < maxRetries) {
      connectionAttempts++;
      console.log(`Attempting reconnection ${connectionAttempts}/${maxRetries}`);
      
      retryTimeout = setTimeout(() => {
        // Close existing connection
        eventSource.close();
        // Start new connection
        streamAssistantResponseWithState(threadId, onStateUpdate, currentState);
      }, 2000 * connectionAttempts); // Exponential backoff
    } else {
      console.error("Max reconnection attempts reached");
      updateState({
        error: "Connection failed after multiple attempts. Please check if the server is running.",
        isStreaming: false
      });
    }
  };

  eventSource.onopen = (event) => {
    console.log("=== SSE CONNECTION OPENED ===");
    console.log("Event:", event);
    console.log("ReadyState:", eventSource.readyState);
    connectionAttempts = 0; // Reset on successful connection
    
    // Clear any existing retry timeout
    if (retryTimeout) {
      clearTimeout(retryTimeout);
    }
  };

  eventSource.onmessage = (event) => {
    try {

      console.log("=== SSE MESSAGE RECEIVED ===");
      console.log("Raw data:", event.data);
      console.log("Event type:", event.type);
      console.log("Last event ID:", event.lastEventId);

      if (!event.data || event.data.trim() === '') {
        console.log("Received empty message, ignoring");
        return;
      }


      const data: StreamMessage = JSON.parse(event.data);
      console.log("Parsed data:", data);


      // Handle connection test messages
      if (data.status === "connected" || data.status === "connection_test") {
        console.log("Connection test successful");
        return;
      }


      // Handle different message types
      if (data.error) {
        console.error("Stream error:", data.error);
        updateState({
          error: data.error,
          isStreaming: false
        });
        eventSource.close();
        return;
      }

      // Handle interrupt
      if (data.chat_type === "interrupt") {
        console.log("Graph interrupted, waiting for user input");
        console.log("Interrupt message:", data.message);
        updateState({
          isInterrupted: true,
          isStreaming: false,
          interruptMessage: data.message || "Please choose the next action",
          availableChoices: ROUTING_CHOICES,
          // IMPORTANT: Clear artifact feedback state when showing routing choice
          requiresArtifactFeedback: false,
          pendingFeedbackArtifactId: undefined
        });
        eventSource.close(); // Close the stream, will be resumed after user choice
        return;
      }

      // Handle artifact feedback requirement
      if (data.chat_type === "artifact_feedback_required" || data.status === "artifact_feedback_required") {
        console.log("Artifact feedback required for artifact:", data.pending_artifact_id);
        updateState({
          requiresArtifactFeedback: true,
          pendingFeedbackArtifactId: data.pending_artifact_id,
          isStreaming: false
        });
        eventSource.close(); // Close the stream, will be resumed after artifact feedback
        return;
      }

      if (data.status) {
        console.log("Status update:", data.status);
        const status = data.status; // Extract to avoid type narrowing issues
        
        if (status === "user_feedback") {
          updateState({
            requiresFeedback: true,
            isStreaming: false
          });
          eventSource.close();
          return;
        }
        
        if (status === "finished") {
          updateState({
            isComplete: true,
            isStreaming: false,
            // Keep artifacts and messages, just mark as complete
          });
          eventSource.close();
          return;
        }
        
        if (status === "completed") {
          updateState({
            isStreaming: false,
            isComplete: false
          });
        }
        
        if (status === "waiting_for_user_input") {
          updateState({
            isInterrupted: true,
            isStreaming: false,
            interruptMessage: data.message || "Please choose the next action",
            availableChoices: ROUTING_CHOICES
          });
          eventSource.close();
          return;
        }
        
      }

      // Handle conversation content
      if (data.chat_type === "conversation" && data.content) {
        console.log(`Adding content from ${data.agent || 'Unknown'} (${data.node}):`, data.content);
        
        // ADD MESSAGE TO ACCUMULATION instead of overwriting
        addMessage({
          role: "assistant",
          text: data.content,
          agent: data.agent,
          timestamp: data.timestamp || new Date().toISOString(),
          artifact_id: data.artifact_id,
          isComplete: true
        });

        updateState({
          chatType: "conversation",
          currentNode: data.node,
          isStreaming: false
        });
      }

      // Handle routing decisions
      if (data.chat_type === "routing_decision" && data.content) {
        console.log(`Routing decision: ${data.content}`);
        
        // Create a better routing message using node labels
        let routingMessage = data.content;

        const routingMatch = data.content.match(/Routing to:\s*(.+)/i);
        if (routingMatch) {
          const nodeValue = routingMatch[1].trim();
          const choice = ROUTING_CHOICES.find(item => item.value === nodeValue);

          if (!choice) {
            throw new Error(`Invalid routing value: "${nodeValue}" not found in ROUTING_CHOICES`);
          }

          routingMessage = `Now routing to: ${choice.label}`;
        }
        
        // ADD MESSAGE TO ACCUMULATION instead of overwriting
        addMessage({
          role: "assistant",
          text: routingMessage,
          agent: "System",
          timestamp: data.timestamp || new Date().toISOString(),
          isComplete: true
        });

        updateState({
          chatType: "conversation",
          currentNode: data.node,
          isStreaming: false
        });
      }

      // Handle artifact creation
      if (data.chat_type === "artifact") {
        console.log("Frontend received artifact:", data.artifact_id, "version:", data.version);
        console.log(`Artifact created by ${data.agent}: ${data.artifact_type}`);
        console.log("Raw artifact data:", data);
        
        // The content is already parsed as a JavaScript object, don't parse it again
        const parsedContent = data.content || null;
        console.log("Artifact content (already parsed):", parsedContent);
        
        const newArtifact: ArtifactInfo = {
          id: data.artifact_id || '',
          type: data.artifact_type || '',
          agent: data.agent || '',
          version: data.version || '1.0',
          timestamp: data.timestamp || new Date().toISOString(),
          status: data.status || 'completed',
          content: parsedContent  // Use directly, don't parse again
        };

        console.log("Adding artifact to state:", newArtifact.id);
        // Add to existing artifacts instead of replacing
        addArtifact(newArtifact);

        updateState({
          chatType: "artifact",
          currentAgent: data.agent,
          currentNode: data.node
        });

        // Check if this artifact requires feedback (when status is "completed" and no other pending states)
        if (data.status === "completed" && !currentState.requiresFeedback && !currentState.isInterrupted) {
          console.log("Artifact completed, may require feedback");
          // Note: The backend will send a separate message if feedback is required
        }
      }

      // Handle errors
      if (data.chat_type === "error") {
        console.error(`Error in ${data.node} (${data.agent}):`, data.content);
        updateState({
          error: `Error in ${data.node}: ${data.content}`,
          currentAgent: data.agent,
          currentNode: data.node
        });
      }

      if (data.thread_id && !currentState.threadId) {
        updateState({
          threadId: data.thread_id
        });
      }

    } catch (parseError) {
      console.error("=== SSE PARSE ERROR ===");
        console.error("Parse error:", parseError);
        console.error("Raw data was:", event.data);
        console.error("Data type:", typeof event.data);
        console.error("Data length:", event.data?.length);
        
        updateState({
          error: `Failed to parse server message: ${parseError}`,
          isStreaming: false
      });
    }
  };


  eventSource.onerror = (error) => {
      console.error("=== SSE ERROR EVENT ===");
      console.error("Error object:", error);
      console.error("EventSource readyState:", eventSource.readyState);
      console.error("EventSource URL:", eventSource.url);
      
      // ReadyState meanings:
      // 0 = CONNECTING
      // 1 = OPEN  
      // 2 = CLOSED
      
      switch (eventSource.readyState) {
        case EventSource.CONNECTING:
          console.error("Connection is being attempted");
          updateState({
            error: "Attempting to connect to server...",
            isStreaming: true // Keep as streaming during connection attempts
          });
          break;
          
        case EventSource.OPEN:
          console.error("Connection is open but received error");
          updateState({
            error: "Connection error while streaming",
            isStreaming: false
          });
          break;
          
        case EventSource.CLOSED:
          console.error("Connection is closed");
          updateState({
            error: "Connection closed by server",
            isStreaming: false
          });
          
          // Try to reconnect if it wasn't a manual close
          if (connectionAttempts < maxRetries) {
            console.log("Attempting reconnection...");
            attemptReconnection();
          }
          break;
          
        default:
          console.error("Unknown readyState:", eventSource.readyState);
          updateState({
            error: "Unknown connection state",
            isStreaming: false
          });
      }
    };
    return eventSource;
}

// Update the original streamAssistantResponse to use the new function
function streamAssistantResponse(
  threadId: string, 
  onStateUpdate: (state: ConversationState) => void
) {
  return streamAssistantResponseWithState(threadId, onStateUpdate, undefined);
}

// Function to resume streaming after feedback
async function resumeStream(
  threadId: string, 
  reviewAction: string, 
  onStateUpdate: (state: ConversationState) => void,
  humanComment?: string
) {
  try {
    console.log("Resuming stream:", { threadId, reviewAction, humanComment });
    
    const resumeRes = await fetch("http://localhost:8000/graph/stream/resume", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        thread_id: threadId,
        resume_type: "feedback",
        review_action: reviewAction,
        human_comment: humanComment
      }),
    });

    if (!resumeRes.ok) {
      const errorText = await resumeRes.text();
      console.error("Resume request failed:", errorText);
      throw new Error(`Failed to resume: ${resumeRes.status} ${resumeRes.statusText}`);
    }

    const resumeData = await resumeRes.json();
    console.log("Resume response:", resumeData);
    
    streamAssistantResponse(threadId, onStateUpdate);
    
  } catch (error) {
    console.error("Error in resumeStream:", error);
    
    // Update state with error
    const errorState: ConversationState = {
      currentMessage: "",
      isStreaming: false,
      chatType: null,
      threadId,
      requiresFeedback: false,
      isComplete: false,
      error: error instanceof Error ? error.message : "Failed to resume stream",
      artifacts: [],
      isInterrupted: false,
      requiresArtifactFeedback: false,
      messages: []
    };

    onStateUpdate(errorState);
  }
}

// Function to send routing choice from user input and resume graph
async function sendRoutingChoice(
  threadId: string,
  userChoice: string,
  onStateUpdate: (state: ConversationState) => void,
  currentState?: ConversationState
) {
  try {
    console.log("Sending routing choice:", { threadId, userChoice });

    // Send the routing choice to your existing resume endpoint
    const resumeRes = await fetch("http://localhost:8000/graph/stream/resume", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        thread_id: threadId,
        resume_type: "routing_choice",
        user_choice: userChoice
      }),
    });

    if (!resumeRes.ok) {
      const errorText = await resumeRes.text();
      console.error("Resume request failed:", errorText);
      throw new Error(`Failed to resume: ${resumeRes.status} ${resumeRes.statusText}`);
    }

    const resumeData = await resumeRes.json();
    console.log("Resume response:", resumeData);

    // Clear interrupt state but PRESERVE artifacts and messages
    // Update state first
    const updatedState = currentState ? {
      ...currentState,
      isStreaming: true,
      isInterrupted: false,
      interruptMessage: undefined,
      availableChoices: undefined,
      requiresArtifactFeedback: false,
      currentMessage: ""
    } : {
      currentMessage: "",
      isStreaming: true,
      chatType: null,
      threadId,
      requiresFeedback: false,
      isComplete: false,
      error: null,
      artifacts: [],
      isInterrupted: false,
      interruptMessage: undefined,
      availableChoices: undefined,
      requiresArtifactFeedback: false,
      messages: []
    };

    onStateUpdate(updatedState);

    // Then start streaming again WITH PRESERVED STATE
    setTimeout(() => {
      streamAssistantResponseWithState(threadId, onStateUpdate, updatedState);
    }, 500);
    
  } catch (error) {
    console.error("Error in sendRoutingChoice:", error);
    
    // Update state with error
    const errorState: ConversationState = {
      currentMessage: "",
      isStreaming: false,
      chatType: null,
      threadId,
      requiresFeedback: false,
      isComplete: false,
      error: error instanceof Error ? error.message : "Failed to send routing choice",
      artifacts: [],
      isInterrupted: false,
      requiresArtifactFeedback: false,
      messages: []
    };

    onStateUpdate(errorState);
  }
}

// NEW: Function to send artifact feedback (accept/feedback) from user input 
async function sendArtifactFeedback(
  threadId: string,
  artifactId: string,
  action: "accept" | "feedback",
  feedbackText: string | null,
  onStateUpdate: (state: ConversationState) => void,
  currentState?: ConversationState
) {
  try {
    console.log("Sending artifact feedback:", { threadId, artifactId, action, feedbackText });
    
    // Send the artifact feedback to the resume endpoint
    const resumeRes = await fetch("http://localhost:8000/graph/stream/resume", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        thread_id: threadId,
        resume_type: "artifact_feedback",
        artifact_id: artifactId,
        artifact_action: action,
        artifact_feedback: feedbackText
      }),
    });

    if (!resumeRes.ok) {
      const errorText = await resumeRes.text();
      console.error("Artifact feedback request failed:", errorText);
      throw new Error(`Failed to send artifact feedback: ${resumeRes.status} ${resumeRes.statusText}`);
    }

    const resumeData = await resumeRes.json();
    console.log("Artifact feedback response:", resumeData);
    
    // Clear only artifact feedback specific states, keep everything else
    // IMPORTANT: Don't clear interrupt state here - let the stream handle it
    const updatedState = currentState ? {
      ...currentState,
      requiresArtifactFeedback: false,
      pendingFeedbackArtifactId: undefined,
      isStreaming: true,
      currentMessage: ""
    } : undefined;

    if (updatedState) {
      onStateUpdate(updatedState);
    }

    // Start streaming again with preserved state
    // Add a small delay to prevent immediate reconnection issues
    setTimeout(() => {
      streamAssistantResponseWithState(threadId, onStateUpdate, updatedState);
    }, 500);
    
  } catch (error) {
    console.error("Error in sendArtifactFeedback:", error);
    
    // Update state with error but preserve existing data
    if (currentState) {
      onStateUpdate({
        ...currentState,
        error: error instanceof Error ? error.message : "Failed to send artifact feedback",
        isStreaming: false
      });
    }
  }
}

/**
 * Export an artifact as PDF
 * @param threadId - The thread ID containing the artifact
 * @param artifactId - The artifact ID to export
 */
async function exportArtifactAsPDF(threadId: string, artifactId: string): Promise<void> {
  try {
    console.log("Exporting artifact as PDF:", { threadId, artifactId });

    const response = await fetch("http://localhost:8000/graph/export_pdf", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        thread_id: threadId,
        artifact_id: artifactId,
      }),
    });

    if (!response.ok) {
      const errorText = await response.text();
      throw new Error(`Failed to export PDF: ${response.status} ${response.statusText}\n${errorText}`);
    }

    // Get the PDF blob
    const blob = await response.blob();

    // Create a download link
    const url = window.URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `${artifactId}.pdf`;
    document.body.appendChild(a);
    a.click();

    // Cleanup
    window.URL.revokeObjectURL(url);
    document.body.removeChild(a);

    console.log("PDF export successful");
  } catch (error) {
    console.error("Error exporting artifact as PDF:", error);
    throw error;
  }
}

export {
  sendUserPrompt,
  resumeStream,
  sendRoutingChoice,
  sendArtifactFeedback,
  exportArtifactAsPDF,
  ROUTING_CHOICES,
  type ConversationState,
  type ConversationMessage,
  type ArtifactInfo
};