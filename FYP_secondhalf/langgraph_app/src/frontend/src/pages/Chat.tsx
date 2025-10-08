// Chat.tsx - COMPLETE FILE WITH ARTIFACT ACCEPT/FEEDBACK FEATURE
import { useState, useMemo, useEffect } from "react";
import { sendUserPrompt, resumeStream, sendRoutingChoice, sendArtifactFeedback, exportArtifactAsPDF, ROUTING_CHOICES, type ConversationState, type ConversationMessage, type ArtifactInfo } from "../api/chat/routes";
import {
  PromptInput,
  PromptInputButton,
  PromptInputModelSelect,
  PromptInputModelSelectContent,
  PromptInputModelSelectItem,
  PromptInputModelSelectTrigger,
  PromptInputModelSelectValue,
  PromptInputSubmit,
  PromptInputTextarea,
  PromptInputToolbar,
  PromptInputTools,
} from "@/components/ai-elements/prompt-input";
import { GlobeIcon, MicIcon, FileTextIcon, CodeIcon, ImageIcon, DownloadIcon, EyeIcon, CheckIcon, MessageSquareIcon } from "lucide-react";
import {
  Conversation,
  ConversationContent,
  ConversationScrollButton,
} from "@/components/ai-elements/conversation";
import { Message, MessageContent } from "@/components/ai-elements/message";
import { Response } from "@/components/ai-elements/response";
import { Button } from "@/components/ui/button";

// Basic Badge Component
const Badge = ({ children, variant = "default", className = "" }: { 
  children: React.ReactNode; 
  variant?: "default" | "secondary" | "destructive" | "outline";
  className?: string;
}) => {
  const baseClasses = "inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium";
  const variantClasses = {
    default: "bg-blue-100 text-blue-800",
    secondary: "bg-gray-100 text-gray-800", 
    destructive: "bg-red-100 text-red-800",
    outline: "border border-gray-300 text-gray-700"
  };
  
  return (
    <span className={`${baseClasses} ${variantClasses[variant]} ${className}`}>
      {children}
    </span>
  );
};

// Basic Card Components
const Card = ({ children, className = "", onClick }: { 
  children: React.ReactNode; 
  className?: string;
  onClick?: () => void;
}) => (
  <div className={`bg-white border border-gray-200 rounded-lg shadow-sm ${className}`} onClick={onClick}>
    {children}
  </div>
);

const CardHeader = ({ children, className = "" }: { children: React.ReactNode; className?: string }) => (
  <div className={`px-4 py-3 ${className}`}>{children}</div>
);

const CardContent = ({ children, className = "" }: { children: React.ReactNode; className?: string }) => (
  <div className={`px-4 pb-4 ${className}`}>{children}</div>
);

const CardTitle = ({ children, className = "" }: { children: React.ReactNode; className?: string }) => (
  <h3 className={`font-medium ${className}`}>{children}</h3>
);

const CardDescription = ({ children, className = "" }: { children: React.ReactNode; className?: string }) => (
  <p className={`text-gray-600 ${className}`}>{children}</p>
);

// Available models
const models = [
  { id: "gpt-4o", name: "GPT-4o" },
  { id: "claude-opus-4-20250514", name: "Claude 4 Opus" },
];

// Artifact type icons and labels mapping
const getArtifactInfo = (type: string) => {
  switch (type) {
    case "operating_env_list":
      return { icon: <FileTextIcon className="h-4 w-4" />, label: "Operating Environment List", color: "bg-blue-100 text-blue-800" };
    case "requirements_classification":
      return { icon: <FileTextIcon className="h-4 w-4" />, label: "Requirements Classification", color: "bg-green-100 text-green-800" };
    case "system_requirements":
      return { icon: <FileTextIcon className="h-4 w-4" />, label: "System Requirements", color: "bg-purple-100 text-purple-800" };
    case "requirements_model":
      return { icon: <CodeIcon className="h-4 w-4" />, label: "Requirements Model", color: "bg-orange-100 text-orange-800" };
    case "software_requirement_specs":
      return { icon: <FileTextIcon className="h-4 w-4" />, label: "Software Requirement Specs", color: "bg-indigo-100 text-indigo-800" };
    case "review_document":
      return { icon: <FileTextIcon className="h-4 w-4" />, label: "Review Document", color: "bg-red-100 text-red-800" };
    case "validation_report":
      return { icon: <FileTextIcon className="h-4 w-4" />, label: "Validation Report", color: "bg-yellow-100 text-yellow-800" };
    default:
      return { icon: <FileTextIcon className="h-4 w-4" />, label: type, color: "bg-gray-100 text-gray-800" };
  }
};

// Format timestamp for display
const formatTimestamp = (timestamp: string) => {
  try {
    return new Date(timestamp).toLocaleString();
  } catch {
    return timestamp;
  }
};

// Artifact Content Viewer Component
const ArtifactContentViewer = ({ artifact, onClose, threadId }: { artifact: ArtifactInfo & { content?: any }; onClose: () => void; threadId: string | null }) => {
  console.log("Viewing artifact:", artifact);
  console.log("Artifact content:", artifact.content);
  console.log("Artifact type:", artifact.type);

  const [isExporting, setIsExporting] = useState(false);

  const handleExport = async () => {
    if (!threadId) {
      console.error("No thread ID available for export");
      return;
    }

    setIsExporting(true);
    try {
      await exportArtifactAsPDF(threadId, artifact.id);
    } catch (error) {
      console.error("Failed to export PDF:", error);
      alert("Failed to export PDF. Please try again.");
    } finally {
      setIsExporting(false);
    }
  };
  
  const renderContent = () => {
    if (!artifact.content) {
      return (
        <div className="text-center text-gray-500 mt-8">
          <div className="text-lg mb-2">No content available</div>
          <div className="text-sm">
            This artifact doesn't contain content data. 
            <br />Check if the backend is properly serializing Pydantic models.
          </div>
        </div>
      );
    }

    switch (artifact.type) {
      case "requirements_classification":
        const reqClass = artifact.content;
        return (
          <div className="space-y-4">
            <h3 className="font-semibold text-lg">Requirements Classification</h3>
            {reqClass.req_class_id?.map((req: any, idx: number) => (
              <Card key={idx} className="border-l-4 border-l-blue-500">
                <CardHeader className="pb-2">
                  <div className="flex justify-between items-start">
                    <CardTitle className="text-sm">{req.requirement_id}</CardTitle>
                    <div className="flex gap-2">
                      <Badge variant={req.priority === 'High' ? 'destructive' : req.priority === 'Medium' ? 'default' : 'secondary'}>
                        {req.priority}
                      </Badge>
                      <Badge variant="outline">{req.category}</Badge>
                    </div>
                  </div>
                </CardHeader>
                <CardContent>
                  <p className="text-sm text-gray-700">{req.requirement_text}</p>
                </CardContent>
              </Card>
            ))}
          </div>
        );

      case "system_requirements":
        const sysReq = artifact.content;
        return (
          <div className="space-y-4">
            <h3 className="font-semibold text-lg">System Requirements List</h3>
            {sysReq.srl?.map((req: any, idx: number) => (
              <Card key={idx} className="border-l-4 border-l-purple-500">
                <CardHeader className="pb-2">
                  <div className="flex justify-between items-start">
                    <CardTitle className="text-sm">{req.requirement_id}</CardTitle>
                    <div className="flex gap-2">
                      <Badge variant={req.priority === 'High' ? 'destructive' : req.priority === 'Medium' ? 'default' : 'secondary'}>
                        {req.priority}
                      </Badge>
                      <Badge variant="outline">{req.category}</Badge>
                    </div>
                  </div>
                </CardHeader>
                <CardContent>
                  <p className="text-sm text-gray-700">{req.requirement_statement}</p>
                </CardContent>
              </Card>
            ))}
          </div>
        );

      case "requirements_model":
        const model = artifact.content;
        console.log("Requirements model artifact content:", model);
        console.log("Has diagram_base64:", !!model?.diagram_base64);
        console.log("Diagram base64 length:", model?.diagram_base64?.length);
        
        return (
          <div className="space-y-4">
            <h3 className="font-semibold text-lg">Requirements Model</h3>
            
            {/* Display generated diagram if available */}
            {model?.diagram_base64 && (
              <Card>
                <CardHeader>
                  <CardTitle className="text-sm">Generated Use Case Diagram</CardTitle>
                </CardHeader>
                <CardContent>
                  <div className="border rounded-lg p-4 bg-white">
                    <img 
                      src={`data:image/png;base64,${model.diagram_base64}`}
                      alt="Requirements Use Case Diagram"
                      className="max-w-full h-auto mx-auto"
                      style={{ maxHeight: '600px' }}
                      onLoad={() => console.log("Image loaded successfully")}
                      onError={(e) => console.error("Image load error:", e)}
                    />
                  </div>
                  {model.diagram_generation_message && (
                    <p className="text-xs text-gray-600 mt-2">
                      {model.diagram_generation_message}
                    </p>
                  )}
                </CardContent>
              </Card>
            )}
            
            {/* Display UML Code */}
            {model?.uml_fmt_content && (
              <Card>
                <CardHeader>
                  <CardTitle className="text-sm">PlantUML Code</CardTitle>
                </CardHeader>
                <CardContent>
                  <pre className="text-xs bg-gray-50 p-4 rounded overflow-x-auto whitespace-pre-wrap font-mono">
                    {model.uml_fmt_content}
                  </pre>
                </CardContent>
              </Card>
            )}
            
            {/* Fallback: display raw content if structure is different */}
            {!model?.uml_fmt_content && !model?.diagram_base64 && (
              <Card>
                <CardHeader>
                  <CardTitle className="text-sm">Content (Fallback)</CardTitle>
                </CardHeader>
                <CardContent>
                  <pre className="text-xs bg-gray-50 p-4 rounded overflow-x-auto whitespace-pre-wrap font-mono">
                    {typeof artifact.content === 'string' ? artifact.content : JSON.stringify(artifact.content, null, 2)}
                  </pre>
                </CardContent>
              </Card>
            )}
          </div>
        );

      case "software_requirement_specs":
        const specs = artifact.content;
        return (
          <div className="space-y-4">
            <h3 className="font-semibold text-lg">Software Requirement Specifications</h3>
            
            <Card>
              <CardHeader>
                <CardTitle className="text-sm">Brief Introduction</CardTitle>
              </CardHeader>
              <CardContent>
                <p className="text-sm text-gray-700">{specs.brief_introduction}</p>
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle className="text-sm">Product Description</CardTitle>
              </CardHeader>
              <CardContent>
                <p className="text-sm text-gray-700">{specs.product_description}</p>
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle className="text-sm">Functional Requirements</CardTitle>
              </CardHeader>
              <CardContent>
                <div className="text-sm text-gray-700 whitespace-pre-wrap">{specs.functional_requirements}</div>
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle className="text-sm">Non-Functional Requirements</CardTitle>
              </CardHeader>
              <CardContent>
                <div className="text-sm text-gray-700 whitespace-pre-wrap">{specs.non_functional_requirements}</div>
              </CardContent>
            </Card>

            {specs.references && (
              <Card>
                <CardHeader>
                  <CardTitle className="text-sm">References</CardTitle>
                </CardHeader>
                <CardContent>
                  <div className="text-sm text-gray-700 whitespace-pre-wrap">{specs.references}</div>
                </CardContent>
              </Card>
            )}
          </div>
        );

      default:
        const content = typeof artifact.content === 'string' 
          ? artifact.content 
          : JSON.stringify(artifact.content, null, 2);
        return (
          <div className="space-y-4">
            <h3 className="font-semibold text-lg">Artifact Content</h3>
            <Card>
              <CardContent className="pt-4">
                <pre className="text-xs bg-gray-50 p-4 rounded overflow-x-auto whitespace-pre-wrap">
                  {content}
                </pre>
              </CardContent>
            </Card>
          </div>
        );
    }
  };

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
      <div className="bg-white rounded-lg shadow-xl w-11/12 h-5/6 flex flex-col">
        <div className="flex justify-between items-center p-4 border-b">
          <div className="flex items-center space-x-2">
            {getArtifactInfo(artifact.type).icon}
            <h2 className="text-lg font-semibold">{getArtifactInfo(artifact.type).label}</h2>
          </div>
          <Button variant="ghost" size="sm" onClick={onClose} className="text-black hover:text-gray-200">
            ✕
          </Button>
        </div>
        
        <div className="flex-1 overflow-y-auto p-4">
          {renderContent()}
        </div>
        
        <div className="border-t p-4 flex justify-between items-center">
          <div className="text-sm text-white">
            Created by {artifact.agent} • {formatTimestamp(artifact.timestamp)}
          </div>
          <Button
            variant="outline"
            size="sm"
            onClick={handleExport}
            disabled={isExporting || !threadId}
          >
            <DownloadIcon className="h-3 w-3 mr-1" />
            {isExporting ? "Exporting..." : "Export as PDF"}
          </Button>
        </div>
      </div>
    </div>
  );
};

// Artifact Card Component (no Accept/Feedback buttons here)
const ArtifactCard = ({ 
  artifact, 
  onClick
}: { 
  artifact: ArtifactInfo; 
  onClick: () => void;
}) => {
  const artifactInfo = getArtifactInfo(artifact.type);
  
  // Check if this is a requirements model with a diagram
  const hasDiagram = artifact.type === "requirements_model" && 
                    artifact.content && 
                    typeof artifact.content === 'object' && 
                    artifact.content.diagram_base64;
  
  return (
    <Card className="mb-3 hover:shadow-md transition-shadow cursor-pointer" onClick={onClick}>
      <CardHeader className="pb-2">
        <div className="flex items-center justify-between">
          <div className="flex items-center space-x-2">
            {artifactInfo.icon}
            <CardTitle className="text-sm">{artifactInfo.label}</CardTitle>
            {hasDiagram && (
              <div title="Contains generated diagram">
                <ImageIcon className="h-3 w-3 text-green-600" />
              </div>
            )}
          </div>
          <div className="flex gap-2">
            <Badge variant={artifact.status === 'completed' ? 'default' : 'secondary'}>
              {artifact.status}
            </Badge>
            <Badge className={artifactInfo.color} variant="secondary">
              {artifact.version}
            </Badge>
          </div>
        </div>
        <CardDescription className="text-xs">
          Created by {artifact.agent} • {formatTimestamp(artifact.timestamp)}
        </CardDescription>
      </CardHeader>
      <CardContent className="pt-0">
        <div className="space-y-2">
          <div className="text-xs text-gray-600 whitespace-normal break-words">
            ID: {artifact.id}
          </div>
          {hasDiagram && (
            <div className="text-xs text-green-600">
              📊 Includes generated diagram
            </div>
          )}
          <div className="flex space-x-2">
            <Button 
              size="sm" 
              className="h-7 text-xs flex-1 bg-white hover:bg-gray-100 text-black border border-gray-300 font-medium"
            >
              <EyeIcon className="h-3 w-3 mr-1" />
              {hasDiagram ? "View Diagram & Code" : "View Content"}
            </Button>
          </div>
        </div>
      </CardContent>
    </Card>
  );
};

const InputDemo = () => {
  // UI-specific state
  const [inputText, setInputText] = useState<string>("");
  const [model, setModel] = useState<string>(models[0].id);
  const [feedbackText, setFeedbackText] = useState<string>("");
  const [showFeedbackInput, setShowFeedbackInput] = useState<boolean>(false);
  const [selectedArtifact, setSelectedArtifact] = useState<ArtifactInfo | null>(null);
  
  // Artifact feedback state
  const [artifactFeedbackText, setArtifactFeedbackText] = useState<string>("");
  const [showArtifactFeedbackInput, setShowArtifactFeedbackInput] = useState<boolean>(false);
  const [pendingFeedbackArtifactId, setPendingFeedbackArtifactId] = useState<string | null>(null);
  
  // Current conversation state from routes.ts (now includes messages array)
  const [conversationState, setConversationState] = useState<ConversationState | null>(null);


  // ADD THIS DEBUG useEffect HERE:
  useEffect(() => {
    console.log("Artifacts in state changed:", conversationState?.artifacts?.map(a => ({ 
      id: a.id, 
      version: a.version, 
      type: a.type,
      timestamp: a.timestamp 
    })));
  }, [conversationState?.artifacts]);


  // Handle state updates from routes.ts
  const handleStateUpdate = (newState: ConversationState) => {
    console.log("State update received:", newState);
    console.log("Messages in state:", newState.messages);
    console.log("Artifacts in state:", newState.artifacts);
    setConversationState(newState);
  };

  // Create grouped messages for rendering from the state messages
  const groupedMessages = useMemo(() => {
    if (!conversationState?.messages) return [];

    const allMessages = [...conversationState.messages];
    
    // Add current streaming message if it exists and is different
    if (conversationState.isStreaming && conversationState.currentMessage) {
      const lastMessage = allMessages[allMessages.length - 1];
      const isDifferentFromLast = !lastMessage || 
        lastMessage.text !== conversationState.currentMessage ||
        lastMessage.agent !== conversationState.currentAgent;
      
      if (isDifferentFromLast) {
        allMessages.push({
          role: "assistant",
          text: conversationState.currentMessage,
          agent: conversationState.currentAgent,
          isComplete: false
        });
      }
    }

    // Add interrupt message if exists
    if (conversationState.isInterrupted && conversationState.interruptMessage) {
      allMessages.push({
        role: "assistant",
        text: conversationState.interruptMessage,
        agent: "System",
        isComplete: true
      });
    }

    // Group consecutive messages by agent
    const grouped: Array<{
      agent: string;
      role: "user" | "assistant";
      messages: Array<{text: string; isComplete: boolean}>;
    }> = [];

    allMessages.forEach((msg) => {
      const currentAgent = msg.role === "user" ? "You" : (msg.agent || "Assistant");
      const lastGroup = grouped[grouped.length - 1];
      
      // If last group has same agent and role, add to it
      if (lastGroup && lastGroup.agent === currentAgent && lastGroup.role === msg.role) {
        lastGroup.messages.push({
          text: msg.text,
          isComplete: msg.isComplete
        });
      } else {
        // Create new group
        grouped.push({
          agent: currentAgent,
          role: msg.role,
          messages: [{
            text: msg.text,
            isComplete: msg.isComplete
          }]
        });
      }
    });

    return grouped;
  }, [conversationState]);

  // Sort artifacts with latest at top (reverse chronological)
  const sortedArtifacts = useMemo(() => {
    if (!conversationState?.artifacts) return [];
    return [...conversationState.artifacts].sort((a, b) => 
      new Date(b.timestamp).getTime() - new Date(a.timestamp).getTime()
    );
  }, [conversationState?.artifacts]);

  // Handle artifact click - show viewer directly since content is always available
  const handleArtifactClick = (artifact: ArtifactInfo) => {
    setSelectedArtifact(artifact);
  };

  // Handle artifact accept
  const handleArtifactAccept = async (artifactId: string) => {
    console.log("handleArtifactAccept called with artifactId:", artifactId);
    console.log("conversationState?.threadId:", conversationState?.threadId);

    if (!conversationState?.threadId) {
      console.error("No threadId available, cannot accept artifact");
      return;
    }

    console.log("About to send artifact feedback for accept");

    // Add user message for accept action
    const acceptMessage: ConversationMessage = {
      role: "user",
      text: `Accepted artifact: ${artifactId}`,
      isComplete: true
    };

    const updatedState = {
      ...conversationState,
      messages: [...conversationState.messages, acceptMessage]
    };

    setConversationState(updatedState);

    try {
      await sendArtifactFeedback(
        conversationState.threadId,
        artifactId,
        "accept",
        null,
        handleStateUpdate,
        updatedState // Pass current state to preserve it
      );
    } catch (error) {
      console.error("Error accepting artifact:", error);
    }
  };

  // Handle artifact feedback initiation
  const handleArtifactFeedbackStart = (artifactId: string) => {
    setPendingFeedbackArtifactId(artifactId);
    setShowArtifactFeedbackInput(true);
  };

  // Handle artifact feedback submission
  const handleArtifactFeedbackSubmit = async () => {
    if (!conversationState?.threadId || !pendingFeedbackArtifactId || !artifactFeedbackText.trim()) return;
    
    // Add user message for feedback action
    const feedbackMessage: ConversationMessage = {
      role: "user",
      text: `Feedback for artifact ${pendingFeedbackArtifactId}: ${artifactFeedbackText}`,
      isComplete: true
    };

    const updatedState = {
      ...conversationState,
      messages: [...conversationState.messages, feedbackMessage]
    };

    setConversationState(updatedState);
    
    try {
      await sendArtifactFeedback(
        conversationState.threadId,
        pendingFeedbackArtifactId,
        "feedback",
        artifactFeedbackText,
        handleStateUpdate,
        updatedState // Pass current state to preserve it
      );
      
      // Clear feedback state
      setArtifactFeedbackText("");
      setShowArtifactFeedbackInput(false);
      setPendingFeedbackArtifactId(null);
    } catch (error) {
      console.error("Error sending artifact feedback:", error);
    }
  };

  // Cancel artifact feedback
  const handleArtifactFeedbackCancel = () => {
    setArtifactFeedbackText("");
    setShowArtifactFeedbackInput(false);
    setPendingFeedbackArtifactId(null);
  };

  // User enters and submit the chat input text
  const handleSubmit = async (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    if (!inputText.trim()) return;

    // Add user message to the state by updating it manually
    const userMessage: ConversationMessage = { 
      role: "user", 
      text: inputText,
      isComplete: true
    };

    // Update state to include the user message
    if (conversationState) {
      setConversationState({
        ...conversationState,
        messages: [...conversationState.messages, userMessage]
      });
    }

    // Clear input
    const currentInput = inputText;
    setInputText("");

    try {
      // Use routes.ts to handle the API communication
      await sendUserPrompt(currentInput, handleStateUpdate);
    } catch (error) {
      console.error("Error sending prompt:", error);
    }
  };

  const handleApprove = async () => {
    if (!conversationState?.threadId) return;
    
    try {
      await resumeStream(
        conversationState.threadId,
        "approved",
        handleStateUpdate,
        "User has approved the feedback."
      );
    } catch (error) {
      console.error("Error approving:", error);
    }
  };

  const handleFeedback = async () => {
    if (!conversationState?.threadId || !feedbackText.trim()) return;

    try {
      await resumeStream(
        conversationState.threadId,
        "feedback", 
        handleStateUpdate,
        feedbackText
      );
      setFeedbackText(""); // Clear feedback text
      setShowFeedbackInput(false); // Hide feedback input
    } catch (error) {
      console.error("Error sending feedback:", error);
    }
  };

  // Handle routing choice selection
  const handleRoutingChoice = async (choice: string) => {
    if (!conversationState?.threadId) return;

    // Add user's routing choice to state
    const choiceLabel = ROUTING_CHOICES.find(c => c.value === choice)?.label || choice;
    const userChoiceMessage: ConversationMessage = { 
      role: "user", 
      text: `Selected: ${choiceLabel}`,
      isComplete: true
    };

    // Update state to include the user choice
    const updatedState = {
      ...conversationState,
      messages: [...conversationState.messages, userChoiceMessage]
    };
    setConversationState(updatedState);

    try {
      await sendRoutingChoice(conversationState.threadId, choice, handleStateUpdate, updatedState);
    } catch (error) {
      console.error("Error sending routing choice:", error);
    }
  };

  // Determine what UI state to show
  const showFeedbackButtons = conversationState?.requiresFeedback && !conversationState.isComplete;
  const showRoutingChoice = conversationState?.isInterrupted && conversationState.availableChoices;
  const isLoading = conversationState?.isStreaming || false;
  
  // Check if we should show artifact accept/feedback buttons
  const showArtifactAcceptFeedback = Boolean(conversationState?.requiresArtifactFeedback && !conversationState.isComplete);
  
  // Block chat input when artifact feedback is required or being provided
  const isChatInputBlocked = isLoading || showArtifactAcceptFeedback || showArtifactFeedbackInput;

  return (
    <div className="fixed inset-4 flex gap-4">
      {/* Chat Panel - Left Side */}
      <div className="flex-1 rounded-lg border h-full py-6 px-4 flex flex-col">
        <div className="flex-grow overflow-y-auto">
          <Conversation>
            <ConversationContent>
              {/* Render grouped messages */}
              {groupedMessages.map((group, groupIdx) => (
                <Message from={group.role} key={groupIdx}>
                  <MessageContent>
                    <div className={`font-bold text-sm mb-2 ${group.agent === "You" ? "text-white" : "text-gray-600"}`}>
                      {group.agent}
                    </div>
                    <div className="space-y-2">
                      {group.messages.map((msg, msgIdx) => (
                        <Response 
                          key={msgIdx}
                          className={!msg.isComplete ? "opacity-70" : ""}
                        >
                          {msg.text}
                        </Response>
                      ))}
                    </div>
                  </MessageContent>
                </Message>
              ))}
              
              {/* Show thread ID for debugging */}
              {conversationState?.threadId && (
                <div className="mt-2 text-sm text-gray-500">
                  Thread ID: {conversationState.threadId}
                </div>
              )}

              {/* Show error if any */}
              {conversationState?.error && (
                <div className="mt-2 text-sm text-red-500">
                  Error: {conversationState.error}
                </div>
              )}
            </ConversationContent>
            <ConversationScrollButton />
          </Conversation>
        </div>

        {/* Conditional UI based on conversation state */}
        {showArtifactFeedbackInput ? (
          // Show artifact feedback input in chat section
          <div className="mt-auto">
            <div className="flex justify-center items-center">
              <div className="bg-grey-100 rounded-lg p-6 w-full flex flex-col items-center max-w-lg">
                <div className="text-center mb-4">
                  <p className="text-xl mb-4">Provide feedback for this artifact:</p>
                  {conversationState?.pendingFeedbackArtifactId && (
                    <p className="text-sm text-gray-600">Artifact ID: {conversationState.pendingFeedbackArtifactId}</p>
                  )}
                </div>
                <div className="w-full space-y-2">
                  <PromptInput>
                    <PromptInputTextarea
                      onChange={(e) => setArtifactFeedbackText(e.target.value)}
                      value={artifactFeedbackText}
                      placeholder="Enter your feedback about this artifact..."
                      className="w-full py-2 px-4 border rounded-md"
                    />
                  </PromptInput>
                  <div className="flex gap-2 mt-2 w-full">
                    <Button 
                      variant="outline" 
                      onClick={handleArtifactFeedbackSubmit} 
                      disabled={!artifactFeedbackText.trim()}
                      className="flex-1 text-black bg-white hover:bg-gray-100 border border-gray-300"
                    >
                      Send Feedback
                    </Button>
                    <Button 
                      variant="outline" 
                      onClick={handleArtifactFeedbackCancel}
                      className="flex-1 text-black bg-white hover:bg-gray-100 border border-gray-300"
                    >
                      Cancel
                    </Button>
                  </div>
                </div>
              </div>
            </div>
          </div>
        ) : showArtifactAcceptFeedback ? (
          // Show artifact accept/feedback buttons in chat section
          <div className="mt-auto">
            <div className="flex justify-center items-center">
              <div className="bg-grey-100 rounded-lg p-6 w-full flex flex-col items-center max-w-lg">
                <div className="text-center mb-4">
                  <p className="text-xl mb-4">A new artifact has been generated!</p>
                  {conversationState?.pendingFeedbackArtifactId && (
                    <p className="text-sm text-gray-600">Artifact ID: {conversationState.pendingFeedbackArtifactId}</p>
                  )}
                  <p className="text-sm text-gray-700 mt-2">Do you want to accept this artifact or provide feedback for improvements?</p>
                </div>
                <div className="flex gap-2 w-full max-w-sm">
                  <Button
                    onClick={() => {
                      console.log("Accept button clicked");
                      console.log("pendingFeedbackArtifactId from state:", conversationState?.pendingFeedbackArtifactId);
                      handleArtifactAccept(conversationState?.pendingFeedbackArtifactId || '');
                    }}
                    className="flex-1 bg-black hover:bg-gray-800 text-black"
                  >
                    <CheckIcon className="h-4 w-4 mr-2" />
                    Accept
                  </Button>
                  <Button
                    onClick={() => {
                      console.log("Feedback button clicked");
                      console.log("pendingFeedbackArtifactId from state:", conversationState?.pendingFeedbackArtifactId);
                      handleArtifactFeedbackStart(conversationState?.pendingFeedbackArtifactId || '');
                    }}
                    className="flex-1 bg-orange-600 hover:bg-orange-700 text-black"
                  >
                    <MessageSquareIcon className="h-4 w-4 mr-2" />
                    Provide Feedback
                  </Button>
                </div>
              </div>
            </div>
          </div>
        ) : showRoutingChoice ? (
          // Show routing choice buttons
          <div className="mt-auto">
            <div className="flex justify-center items-center">
              <div className="bg-grey-100 rounded-lg p-6 w-full flex flex-col items-center max-w-lg">
                <div className="text-center mb-4">
                  <p className="text-xl mb-4 text-black">Choose the next action:</p>
                </div>
                <div className="grid grid-cols-1 gap-2 w-full">
                  {conversationState.availableChoices?.map((choice) => (
                    <Button
                      key={choice.value}
                      onClick={() => handleRoutingChoice(choice.value)}
                      className="w-full text-left justify-start bg-gray-100 hover:bg-gray-200 text-black border border-gray-300 font-medium"
                    >
                      {choice.label}
                    </Button>
                  ))}
                </div>
              </div>
            </div>
          </div>
        ) : showFeedbackButtons ? (
          // Show feedback buttons (existing logic)
          <div className="mt-auto">
            {!showFeedbackInput ? (
              // Show approve/feedback buttons
              <div className="flex justify-center items-center">
                <div className="bg-grey-100 rounded-lg p-6 w-full flex justify-center max-w-sm sm:max-w-md lg:max-w-lg">
                  <div className="text-center">
                    <p className="mb-4 text-xl">
                      Do you approve the provided feedback?
                    </p>
                    <Button onClick={handleApprove} className="mr-4">
                      Approve
                    </Button>
                    <Button onClick={() => setShowFeedbackInput(true)}>
                      Provide Feedback
                    </Button>
                  </div>
                </div>
              </div>
            ) : (
              // Show feedback input
              <div>
                <PromptInput>
                  <PromptInputTextarea
                    onChange={(e) => setFeedbackText(e.target.value)}
                    value={feedbackText}
                    placeholder="Enter your feedback"
                    className="w-full py-2 px-4 border rounded-md"
                  />
                </PromptInput>
                <div className="flex gap-2 mt-2">
                  <Button onClick={handleFeedback} disabled={!feedbackText.trim()}>
                    Send Feedback
                  </Button>
                  <Button 
                    variant="outline" 
                    onClick={() => {
                      setShowFeedbackInput(false);
                      setFeedbackText("");
                    }}
                  >
                    Cancel
                  </Button>
                </div>
              </div>
            )}
          </div>
        ) : (
          // Show normal chat input
          <div className="mt-auto">
            <PromptInput onSubmit={handleSubmit}>
              <PromptInputTextarea
                onChange={(e) => setInputText(e.target.value)}
                value={inputText}
                className="w-full py-2 px-4 border rounded-md"
                disabled={isChatInputBlocked}
                placeholder={isChatInputBlocked ? "Please provide artifact feedback before continuing..." : "Type your message..."}
              />
              <PromptInputToolbar>
                <PromptInputTools>
                  <PromptInputButton>
                    <MicIcon size={16} />
                  </PromptInputButton>
                  <PromptInputButton>
                    <GlobeIcon size={16} />
                    <span>Search</span>
                  </PromptInputButton>
                  <PromptInputModelSelect
                    onValueChange={(value) => setModel(value)}
                    value={model}
                  >
                    <PromptInputModelSelectTrigger>
                      <PromptInputModelSelectValue />
                    </PromptInputModelSelectTrigger>
                    <PromptInputModelSelectContent>
                      {models.map((m) => (
                        <PromptInputModelSelectItem key={m.id} value={m.id}>
                          {m.name}
                        </PromptInputModelSelectItem>
                      ))}
                    </PromptInputModelSelectContent>
                  </PromptInputModelSelect>
                </PromptInputTools>
                <PromptInputSubmit disabled={!inputText.trim() || isChatInputBlocked} />
              </PromptInputToolbar>
            </PromptInput>
          </div>
        )}
      </div>

      {/* Artifacts Panel - Right Side */}
      <div className="w-80 rounded-lg border h-full flex flex-col">
        <div className="p-4 border-b">
          <h3 className="text-lg font-semibold">Artifacts</h3>
          <p className="text-sm text-gray-600">
            {sortedArtifacts.length} artifact{sortedArtifacts.length !== 1 ? 's' : ''}
          </p>
        </div>
        
        <div className="flex-1 overflow-y-auto p-4">
          {sortedArtifacts.length === 0 ? (
            <div className="text-center text-gray-500 mt-8">
              <FileTextIcon className="h-12 w-12 mx-auto mb-2 opacity-50" />
              <p>No artifacts yet</p>
              <p className="text-xs mt-1">Artifacts will appear here as they are created</p>
            </div>
          ) : (
            <div className="space-y-2">
              {sortedArtifacts.map((artifact, idx) => (
                <ArtifactCard 
                  key={`${artifact.id}-${idx}`} 
                  artifact={artifact} 
                  onClick={() => handleArtifactClick(artifact)}
                />
              ))}
            </div>
          )}
        </div>
      </div>

      {/* Artifact Content Viewer Modal */}
      {selectedArtifact && (
        <ArtifactContentViewer
          artifact={selectedArtifact}
          onClose={() => setSelectedArtifact(null)}
          threadId={conversationState?.threadId || null}
        />
      )}
    </div>
  );
};

export default InputDemo;