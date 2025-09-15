// src/routes.ts

async function sendUserPrompt(prompt: string) {
  // Step 1: Create a new stream
  const createRes = await fetch("http://localhost:8000/graph/stream/create", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      string_input: prompt,
    }),
  });

  const createData = await createRes.json();
  const threadId = createData.thread_id;

  console.log("Thread started:", threadId);

  // Step 2: Start streaming from backend
  streamAssistantResponse(threadId);
}

function streamAssistantResponse(threadId: string) {
  const eventSource = new EventSource(
    `http://localhost:8000/graph/stream/${threadId}`
  );

  eventSource.onmessage = (event) => {
    console.log("Stream chunk:", event.data);
    // Here you would update your UI state to append the streamed text
  };

  eventSource.onerror = () => {
    console.error("Streaming error");
    eventSource.close();
  };
}

export { sendUserPrompt };
