// Chat.tsx
import { useState } from "react";
import { sendUserPrompt, resumeStream, type ConversationState } from "../api/chat/routes";
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


//1. add a complete message to chat history
//2. let user inputs feedback text and appends the text for "user" role 
//3. handles user approval of feedback 
//4. renders the messages from langgraph
//5. displays error and thread id

const InputDemo = () => {
  // UI-specific state
  const [inputText, setInputText] = useState<string>("");
  const [model, setModel] = useState<string>(models[0].id);
  const [feedbackText, setFeedbackText] = useState<string>("");
  const [showFeedbackInput, setShowFeedbackInput] = useState<boolean>(false);
  
  // Chat history (separate from streaming state)
  const [messages, setMessages] = useState<
  { role: "user" | "assistant"; text: string; agent?: string }[]
>([]);

  
  // Current conversation state from routes.ts
  const [conversationState, setConversationState] = useState<ConversationState | null>(null);

  // Handle state updates from routes.ts
  const handleStateUpdate = (newState: ConversationState) => {
    setConversationState(newState);
    
    // If we have a complete message, add it to chat history
    if (newState.currentMessage && (newState.isComplete || newState.requiresFeedback)) {
      setMessages(prev => {
        const lastMessage = prev[prev.length - 1];
        if (!lastMessage || lastMessage.text !== newState.currentMessage) {
          return [
            ...prev, 
            { 
              role: "assistant", 
              text: newState.currentMessage, 
              agent: newState.currentAgent
            }
          ];
        }
        return prev;
      });
}

  };

  // User enters and submit the chat input text
  const handleSubmit = async (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    if (!inputText.trim()) return;

    // Add user message to chat history
    const userMessage = { role: "user" as const, text: inputText };
    setMessages(prev => [...prev, userMessage]);

    // Clear input
    const currentInput = inputText;
    setInputText("");

    try {
      // Use routes.ts to handle the API communication
      await sendUserPrompt(currentInput, handleStateUpdate);
    } catch (error) {
      console.error("Error sending prompt:", error);
      // Handle error state - could show error message in UI
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

  // Determine what UI state to show
  const showFeedbackButtons = conversationState?.requiresFeedback && !conversationState.isComplete;
  const isLoading = conversationState?.isStreaming || false;

  return (
    <div className="fixed left-10 top-10 right-10 w-full sm:w-1/2 rounded-lg border h-[90vh] py-6 px-4 flex flex-col">
      <div className="flex-grow overflow-y-auto">
        <Conversation>
          <ConversationContent>
            {/* Show completed messages */}
            {messages.map((message, idx) => (
              <Message from={message.role} key={idx}>
                <MessageContent>
                  <div className="font-bold text-sm text-gray-600">
                    {message.role === "user" ? "You" : message.agent || "Assistant"}
                  </div>
                  <Response>{message.text}</Response>
                </MessageContent>
              </Message>
            ))}
            
            {/* Show current streaming message */}
            {conversationState?.isStreaming && conversationState.currentMessage && (
              <Message from="assistant">
                <MessageContent>
                  <div className="font-bold text-sm text-gray-600">
                    {conversationState.currentAgent || "Assistant"}
                  </div>
                  <Response>{conversationState.currentMessage}</Response>
                </MessageContent>
              </Message>
            )}

            
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
        {showFeedbackButtons ? (
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