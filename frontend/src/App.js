// Frontend: React.js with a ChatGPT-like Interface
// Create a React project and install axios

import React, { useState, useEffect } from 'react';
import axios from 'axios';
import ReactMarkdown from 'react-markdown';
import './App.css';  // For styling

function App() {
  const [messages, setMessages] = useState([]);
  const [userInput, setUserInput] = useState('');
  const [isThinking, setIsThinking] = useState(false);

  const handleSendMessage = async () => {
    if (userInput.trim() === '') return;

    const newMessages = [...messages, { sender: 'user', text: userInput }];
    setMessages(newMessages);
    setUserInput('');
    setIsThinking(true);

    try {
      const response = await axios.post('http://127.0.0.1:8000/api/query', { text: userInput });
      const botResponse = response.data.response;
      
      setMessages([...newMessages, { sender: 'bot', text: botResponse }]);
    } catch (error) {
      console.error('Error querying the server:', error);
      setMessages([...newMessages, { sender: 'bot', text: 'An error occurred.' }]);
    } finally {
      setIsThinking(false);
    }
  };

  const handleKeyPress = (event) => {
    if (event.key === 'Enter' && !event.shiftKey) {
      event.preventDefault();
      handleSendMessage();
    }
  };

  return (
    <div className="App">
      <header className="chat-header">
        <img src={process.env.PUBLIC_URL + '/logo.png'} alt="ToddGPT Logo" className="chat-logo" />
        <h1 className="chat-title">ToddGPT</h1>
      </header>
      <div className="chat-container">
        {messages.map((message, index) => (
          <div key={index} className={`chat-message ${message.sender}`}>
            <div className="message-text">
              {message.sender === 'user' ? (
                <p>{message.text}</p>
              ) : (
                <ReactMarkdown>{message.text}</ReactMarkdown>
              )}
            </div>
          </div>
        ))}
        {isThinking && <div className="chat-message bot">
          <div className="message-text thinking">Thinking...</div>
        </div>}
      </div>
      <div className="input-container">
        <input
          type="text"
          value={userInput}
          onChange={(e) => setUserInput(e.target.value)}
          onKeyPress={handleKeyPress}
          placeholder="Type your message..."
          className="chat-input"
        />
        <button onClick={handleSendMessage} className="send-button">Send</button>
      </div>
    </div>
  );
}

export default App;
// CSS (App.css)
