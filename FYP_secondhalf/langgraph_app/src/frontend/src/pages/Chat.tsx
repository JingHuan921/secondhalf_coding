// Chat.tsx - SIMPLIFIED VERSION USING STATE MESSAGES
import { useState, useMemo } from "react";
import { sendUserPrompt, resumeStream, sendRoutingChoice, ROUTING_CHOICES, type ConversationState, type ConversationMessage } from "../api/chat/routes";
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
import { GlobeIcon, MicIcon } from "lucide-react";
import {
  Conversation,
  ConversationContent,
  ConversationScrollButton,
} from "@/components/ai-elements/conversation";
import { Message, MessageContent } from "@/components/ai-elements/message";
import { Response } from "@/components/ai-elements/response";
import { Button } from "@/components/ui/button";

// Available models
const models = [
  { id: "gpt-4o", name: "GPT-4o" },
  { id: "claude-opus-4-20250514", name: "Claude 4 Opus" },
];

const InputDemo = () => {
  // UI-specific state
  const [inputText, setInputText] = useState<string>("");
  const [model, setModel] = useState<string>(models[0].id);
  const [feedbackText, setFeedbackText] = useState<string>("");
  const [showFeedbackInput, setShowFeedbackInput] = useState<boolean>(false);
  
  // Current conversation state from routes.ts (now includes messages array)
  const [conversationState, setConversationState] = useState<ConversationState | null>(null);

  // Handle state updates from routes.ts
  const handleStateUpdate = (newState: ConversationState) => {
    console.log("State update received:", newState);
    console.log("Messages in state:", newState.messages);
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
    setConversationState({
      ...conversationState,
      messages: [...conversationState.messages, userChoiceMessage]
    });

    try {
      await sendRoutingChoice(conversationState.threadId, choice, handleStateUpdate);
    } catch (error) {
      console.error("Error sending routing choice:", error);
    }
  };

  // Determine what UI state to show
  const showFeedbackButtons = conversationState?.requiresFeedback && !conversationState.isComplete;
  const showRoutingChoice = conversationState?.isInterrupted && conversationState.availableChoices;
  const isLoading = conversationState?.isStreaming || false;

  return (
    <div className="fixed left-10 top-10 right-10 w-full sm:w-1/2 rounded-lg border h-[90vh] py-6 px-4 flex flex-col">
      <div className="flex-grow overflow-y-auto">
        <Conversation>
          <ConversationContent>
            {/* Render grouped messages */}
            {groupedMessages.map((group, groupIdx) => (
              <Message from={group.role} key={groupIdx}>
                <MessageContent>
                  <div className="font-bold text-sm text-gray-600 mb-2">
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
      {showRoutingChoice ? (
        // Show routing choice buttons
        <div className="mt-auto">
          <div className="flex justify-center items-center">
            <div className="bg-grey-100 rounded-lg p-6 w-full flex flex-col items-center max-w-lg">
              <div className="text-center mb-4">
                <p className="text-xl mb-4">Choose the next action:</p>
              </div>
              <div className="grid grid-cols-1 gap-2 w-full">
                {conversationState.availableChoices?.map((choice) => (
                  <Button
                    key={choice.value}
                    onClick={() => handleRoutingChoice(choice.value)}
                    className="w-full text-left justify-start"
                    variant="outline"
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
              disabled={isLoading}
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
              <PromptInputSubmit disabled={!inputText.trim() || isLoading} />
            </PromptInputToolbar>
          </PromptInput>
        </div>
      )}
    </div>
  );
};

export default InputDemo;