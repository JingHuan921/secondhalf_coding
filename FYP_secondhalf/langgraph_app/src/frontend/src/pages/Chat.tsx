import { useState, useEffect } from "react";
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
import { Button } from "@/components/ui/button"; // Import the Button component from Shadcn

// Available models
const models = [
  { id: "gpt-4o", name: "GPT-4o" },
  { id: "claude-opus-4-20250514", name: "Claude 4 Opus" },
];

// ---- BACKEND CALL: Create a thread ----
async function createThread(prompt: string) {
  const res = await fetch("http://localhost:8000/graph/stream/create", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      thread_id: "", // optional placeholder
      human_request: prompt, // required by backend
    }),
  });
  if (!res.ok) {
    throw new Error(`Failed to create thread: ${res.statusText}`);
  }

  const data = await res.json();
  console.log("Thread created:", data.thread_id);
  console.log("Status:", data.run_status);
  return data.thread_id;
}

// Start streaming chat output
function startStreaming(
  threadId: string | null,
  setStatus: React.Dispatch<React.SetStateAction<string | null>>,
  setApproveClicked: React.Dispatch<React.SetStateAction<boolean>>,
  setFeedbackClicked: React.Dispatch<React.SetStateAction<boolean>>,
  setMessages: React.Dispatch<
    React.SetStateAction<{ role: "user" | "assistant"; text: string }[]>
  >
) {
  const es = new EventSource(`http://localhost:8000/graph/stream/${threadId}`);
  es.onmessage = (event) => {
    console.log("Raw SSE:", event.data);
    try {
      const parsed = JSON.parse(event.data);
      console.log("Parsed event:", parsed);

      // Handle user feedback status change
      if (parsed.status === "user_feedback") {
        console.log(parsed.status);
        setStatus("user_feedback");
        setApproveClicked(false);
        setFeedbackClicked(false);
      }

      // Handle the end of the process
      if (parsed.status === "finished") {
        console.log("Process finished!");
        setStatus("finished");
      }

      // Handle assistant messages (conversation mode)
      if (parsed.chat_type === "conversation" && parsed.content) {
        const conversationMessage = {
          role: "assistant", // Assuming assistant is sending the message
          text: parsed.content,
        };
        setMessages((prev) => [
          ...prev,
          {
            ...conversationMessage,
            role: conversationMessage.role as "assistant",
          },
        ]);
      }

      // For any other content, you can log or handle accordingly
      if (parsed.content) {
        console.log("Document content:", parsed.content);
      }
    } catch (e) {
      console.error("Error parsing SSE data:", e);
    }
  };

  es.onerror = (err) => {
    console.error("Streaming error:", err);
    es.close();
  };
}

const InputDemo = () => {
  const [text, setText] = useState<string>("");
  const [model, setModel] = useState<string>(models[0].id);
  const [messages, setMessages] = useState<
    { role: "user" | "assistant"; text: string }[]
  >([]);
  const [isLoading, setIsLoading] = useState(false);
  const [threadId, setThreadId] = useState<string | null>(null);
  const [status, setStatus] = useState<string | null>(null); // Manage the status state
  const [approveClicked, setApproveClicked] = useState(false); // Track if 'Approve' is clicked
  const [feedbackClicked, setFeedbackClicked] = useState(false); // Track if 'Feedback' is clicked
  const [feedbackText, setFeedbackText] = useState<string>(""); // Track feedback input text

  const handleSubmit = async (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault(); // Prevent page refresh
    if (!text.trim()) return;

    // Adding user message to the conversation
    const userMessage = { role: "user" as const, text };
    setMessages((prev) => [...prev, userMessage]);

    try {
      setIsLoading(true);

      // Step 1: Create thread
      const id = await createThread(text);
      setThreadId(id);

      // Step 2: Start streaming assistant messages
      startStreaming(
        id,
        setStatus,
        setApproveClicked,
        setFeedbackClicked,
        setMessages
      ); // Pass setMessages to update conversation
    } catch (err) {
      console.error("Error:", err);
    } finally {
      setIsLoading(false);
    }

    setText(""); // Clear the text input after submission
  };

  const handleApprove = async () => {
    console.log("Approved!");

    // Call the backend to resume the graph streaming with 'approved' action
    try {
      const response = await fetch(
        "http://localhost:8000/graph/stream/resume",
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            thread_id: threadId,
            review_action: "approved", // Pass the 'approved' review action
            human_comment: "User has approved the feedback.", // You can customize this message as needed
          }),
        }
      );

      if (!response.ok) {
        throw new Error("Failed to send approval");
      }

      const data = await response.json();
      console.log("Approval sent:", data);
      setApproveClicked(true); // Set approveClicked to true to hide the button

      startStreaming(
        threadId,
        setStatus,
        setApproveClicked,
        setFeedbackClicked,
        setMessages // Pass the setMessages to continue streaming conversation
      );
    } catch (err) {
      console.error("Error during approval:", err);
    }
  };

  const handleFeedback = async (e: React.MouseEvent<HTMLButtonElement>) => {
    e.preventDefault();
    setFeedbackClicked(true);
    if (!feedbackText.trim()) {
      console.log("Feedback is empty!");
      return; // Do nothing if feedback is empty
    }

    console.log("Feedback provided!");

    try {
      const response = await fetch(
        "http://localhost:8000/graph/stream/resume",
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            thread_id: threadId,
            review_action: "feedback", // Pass the 'feedback' review action
            human_comment: feedbackText, // Pass the user-entered feedback
          }),
        }
      );

      if (!response.ok) {
        throw new Error("Failed to send feedback");
      }

      const data = await response.json();
      console.log("Feedback sent:", data);

      setFeedbackClicked(true); // Set feedbackClicked to true to hide the button

      // Clear the feedback input after submission
      setFeedbackText("");

      // After feedback is successfully sent, start streaming again
      startStreaming(
        threadId,
        setStatus,
        setApproveClicked,
        setFeedbackClicked,
        setMessages
      );
    } catch (err) {
      console.error("Error during feedback:", err);
    }
  };

  return (
    <div className="fixed left-10 top-10 right-10 w-full sm:w-1/2 rounded-lg border h-[90vh] py-6 px-4 flex flex-col">
      <div className="flex-grow overflow-y-auto">
        <Conversation>
          <ConversationContent>
            {messages.map((message, idx) => (
              <Message from={message.role} key={idx}>
                <MessageContent>
                  <Response>{message.text}</Response>
                </MessageContent>
              </Message>
            ))}
            {threadId && (
              <div className="mt-2 text-sm text-gray-500">
                Thread ID: {threadId}
              </div>
            )}
          </ConversationContent>
          <ConversationScrollButton />
        </Conversation>
      </div>

      {/* Conditionally render the buttons or chat input based on status */}
      {status === "user_feedback" && !approveClicked && !feedbackClicked ? (
        <div className="mt-auto flex justify-center items-center">
          <div className="bg-grey-100 rounded-lg p-6 w-full flex justify-center max-w-sm sm:max-w-md lg:max-w-lg">
            <div className="text-center">
              <p className="mb-4 text-xl">
                Do you approve the provided feedback?
              </p>
              <Button onClick={handleApprove} className="mr-4">
                Approve
              </Button>
              <Button onClick={handleFeedback}>Feedback</Button>
            </div>
          </div>
        </div>
      ) : feedbackClicked ? (
        <div className="mt-auto">
          <PromptInput onSubmit={handleFeedback}>
            <PromptInputTextarea
              onChange={(e) => setFeedbackText(e.target.value)}
              value={feedbackText}
              placeholder="Enter your feedback"
              className="w-full py-2 px-4 border rounded-md"
            />
            <PromptInputSubmit disabled={!feedbackText || isLoading} />
          </PromptInput>
        </div>
      ) : (
        <div className="mt-auto">
          <PromptInput onSubmit={handleSubmit}>
            <PromptInputTextarea
              onChange={(e) => setText(e.target.value)}
              value={text}
              className="w-full py-2 px-4 border rounded-md"
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
              <PromptInputSubmit disabled={!text || isLoading} />
            </PromptInputToolbar>
          </PromptInput>
        </div>
      )}
    </div>
  );
};

export default InputDemo;
