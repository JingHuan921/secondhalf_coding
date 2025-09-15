import "./App.css";
import { Routes, Route } from "react-router-dom";
import Chat from "./pages/Chat";

// NOTE that if you want to add a function, you will add it to the top of thing hor!

function App() {
  return (
    <main className="MainContent">
      <Routes>
        <Route path="/chat" element={<Chat />} />
      </Routes>
    </main>
  );
}

export default App;
