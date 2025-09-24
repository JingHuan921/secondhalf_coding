// src/routes.ts - FIXED WITH MESSAGE ACCUMULATION

interface StreamMessage {
  thread_id?: string;
  chat_type?: "conversation" | "artifact" | "error" | "interrupt" | "routing_decision";
  content?: string;
  node?: string;
  agent?: string;
  artifact_id?: string;
  artifact_type?: string;
  version?: string;
  timestamp?: string;
  status?: "ready" | "user_feedback" | "finished" | "completed" | "waiting_for_user_input";
  error?: string;
  message?: string; // For interrupt messages
  next_node?: string; // For routing decisions
}

interface ConversationMessage {
  role: "user" | "assistant";
  text: string;
  agent?: string;
  timestamp?: string;
  artifact_id?: string;
  isComplete: boolean;
}

interface ArtifactInfo {
  id: string;
  type: string;
  agent: string;
  version: string;
  timestamp: string;
  status: string;
}

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
  // New interrupt-related fields
  isInterrupted: boolean;
  interruptMessage?: string;
  availableChoices?: Array<{value: string, label: string}>;
  // ADD: Array to store all messages
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

// Receive user prompt and initialize ConversationState to be rendered to frontend
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
      messages: []
    };

    onStateUpdate(errorState);
  }
}

function streamAssistantResponse(
  threadId: string, 
  onStateUpdate: (state: ConversationState) => void
) {
  const streamUrl = `http://localhost:8000/graph/stream/${threadId}`;
  console.log("Starting stream from:", streamUrl);
  
  const eventSource = new EventSource(streamUrl);

  let currentState: ConversationState = {
    currentMessage: "",
    isStreaming: true,
    chatType: null,
    threadId,
    requiresFeedback: false,
    isComplete: false,
    error: null,
    artifacts: [],
    isInterrupted: false,
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

  eventSource.onopen = (event) => {
    console.log("EventSource connection opened");
  };

  eventSource.onmessage = (event) => {
    try {
      console.log("Raw stream data:", event.data);
      const data: StreamMessage = JSON.parse(event.data);
      console.log("Parsed stream chunk:", data);

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
        updateState({
          isInterrupted: true,
          isStreaming: false,
          interruptMessage: data.message || "Please choose the next action",
          availableChoices: ROUTING_CHOICES
        });
        eventSource.close(); // Close the stream, will be resumed after user choice
        return;
      }

      if (data.status) {
        console.log("Status update:", data.status);
        if (data.status === "user_feedback") {
          updateState({
            requiresFeedback: true,
            isStreaming: false
          });
          eventSource.close();
          return;
        } else if (data.status === "finished") {
          updateState({
            isComplete: true,
            isStreaming: false
          });
          eventSource.close();
          return;
        } else if (data.status === "completed") {
          updateState({
            isStreaming: false,
            isComplete: false
          });
        } else if (data.status === "waiting_for_user_input") {
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
        
        // ADD MESSAGE TO ACCUMULATION instead of overwriting
        addMessage({
          role: "assistant",
          text: data.content,
          agent: data.agent || "Routing",
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
        console.log(`Artifact created by ${data.agent}: ${data.artifact_type}`);
        
        const newArtifact: ArtifactInfo = {
          id: data.artifact_id || '',
          type: data.artifact_type || '',
          agent: data.agent || '',
          version: data.version || '1.0',
          timestamp: data.timestamp || new Date().toISOString(),
          status: data.status || 'completed'
        };

        updateState({
          chatType: "artifact",
          currentAgent: data.agent,
          currentNode: data.node,
          artifacts: [...currentState.artifacts, newArtifact]
        });
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
      console.error("Failed to parse stream data:", parseError);
      console.error("Raw data was:", event.data);
      updateState({
        error: "Failed to parse stream data",
        isStreaming: false
      });
      eventSource.close();
    }
  };

  eventSource.onerror = (error) => {
    console.error("EventSource error:", error);
    console.error("EventSource readyState:", eventSource.readyState);
    console.error("EventSource URL:", eventSource.url);
    
    if (eventSource.readyState === EventSource.CLOSED) {
      updateState({
        error: "Connection closed by server. Check if the server is running and supports Server-Sent Events.",
        isStreaming: false
      });
    } else {
      updateState({
        error: "Connection error occurred",
        isStreaming: false
      });
    }
    
    eventSource.close();
  };

  return eventSource;
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
      messages: []
    };

    onStateUpdate(errorState);
  }
}

// NEW: Function to handle routing choice and resume graph
async function sendRoutingChoice(
  threadId: string,
  userChoice: string,
  onStateUpdate: (state: ConversationState) => void
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
    
    // Clear interrupt state and restart streaming
    // Update state first
    onStateUpdate({ 
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
      messages: [] // Keep existing messages - don't clear them
    });
    
    // Then start streaming again
    streamAssistantResponse(threadId, onStateUpdate);
    
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
      messages: []
    };

    onStateUpdate(errorState);
  }
}

export { 
  sendUserPrompt, 
  resumeStream, 
  sendRoutingChoice,
  ROUTING_CHOICES,
  type ConversationState, 
  type ConversationMessage, 
  type ArtifactInfo 
};