// src/routes.ts - UPDATED WITH AGENT SUPPORT AND ARTIFACT STATE

interface StreamMessage {
  thread_id?: string;
  chat_type?: "conversation" | "artifact" | "error";
  content?: string;
  node?: string;
  agent?: string;
  artifact_id?: string;
  artifact_type?: string;
  version?: string;
  timestamp?: string;
  status?: "ready" | "user_feedback" | "finished" | "completed";
  error?: string;
}

interface ConversationMessage {
  role: "user" | "assistant";
  text: string;
  agent?: string;
  timestamp?: string;
  artifact_id?: string;
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
}

async function sendUserPrompt(prompt: string, onStateUpdate: (state: ConversationState) => void) {
  try {
    console.log("Sending prompt:", prompt);
    
    // Step 1: Create a new stream
    const createRes = await fetch("http://localhost:8000/graph/stream/create", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        thread_id: "",
        human_request: prompt,
      }),
    });

    console.log("Create response status:", createRes.status);

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
      artifacts: []
    };

    onStateUpdate(initialState);

    // Step 2: Start streaming from backend
    streamAssistantResponse(threadId, onStateUpdate);

  } catch (error) {
    console.error("Error in sendUserPrompt:", error);
    
    // Update state with error
    const errorState: ConversationState = {
      currentMessage: "",
      isStreaming: false,
      chatType: null,
      threadId: null,
      requiresFeedback: false,
      isComplete: false,
      error: error instanceof Error ? error.message : "Unknown error occurred",
      artifacts: []
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
    artifacts: []
  };

  const updateState = (updates: Partial<ConversationState>) => {
    currentState = { ...currentState, ...updates };
    onStateUpdate(currentState);
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

      if (data.status) {
        console.log("Status update:", data.status);
        if (data.status === "user_feedback") {
          updateState({
            requiresFeedback: true,
            isStreaming: false
          });
        } else if (data.status === "finished") {
          updateState({
            isComplete: true,
            isStreaming: false
          });
        }
        eventSource.close();
        return;
      }

      // Handle conversation content
      if (data.chat_type === "conversation" && data.content) {
        console.log(`Adding content from ${data.agent || 'Unknown'} (${data.node}):`, data.content);
        updateState({
          chatType: "conversation",
          currentMessage: data.content, // For updates mode, we get complete content
          currentAgent: data.agent,
          currentNode: data.node,
          isStreaming: false // Node completed, no longer streaming
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
      artifacts: []
    };

    onStateUpdate(errorState);
  }
}

export { sendUserPrompt, resumeStream, type ConversationState, type ConversationMessage, type ArtifactInfo };