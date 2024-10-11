// Frontend: React.js with a ChatGPT-like Interface
// Create a React project and install axios

import React, { useState, useRef, useEffect } from 'react';
import axios from 'axios';
import ReactMarkdown from 'react-markdown';
import './App.css';  // For styling

const Message = ({ message, index }) => {
  const [expanded, setExpanded] = useState(false);

  return (
    <div key={index} className={`message-container ${message.sender}`}>
      {message.sender === 'bot' && message.responseTime && (
        <div className="response-time">Response time: {message.responseTime}ms</div>
      )}
      <div className="message-wrapper">
        <div className={`chat-message ${message.sender}`}>
          {message.text && (
            <div className="message-text">
              <ReactMarkdown>{message.text}</ReactMarkdown>
            </div>
          )}
          {message.html && (
            <div className="message-html" dangerouslySetInnerHTML={{ __html: message.html }} />
          )}
          {message.image && (
            <img src={message.image} alt="Generated content" />
          )}
        </div>
        {message.sender === 'bot' && (
          <button className="expand-button" onClick={() => setExpanded(!expanded)}>
            {expanded ? '▲' : '▼'}
          </button>
        )}
      </div>
      {message.sender === 'bot' && expanded && message.logging && (
        <div className="message-logging">
          <pre>{message.logging}</pre>
        </div>
      )}
    </div>
  );
};

function App() {
  const [messages, setMessages] = useState([]);
  const [userInput, setUserInput] = useState('');
  const [isThinking, setIsThinking] = useState(false);
  const [conversation, setConversation] = useState([]);
  const chatContainerRef = useRef(null);
  const [imagePaths, setImagePaths] = useState([]);
  const [responseTimes, setResponseTimes] = useState({});

  useEffect(() => {
    if (chatContainerRef.current) {
      chatContainerRef.current.scrollTop = chatContainerRef.current.scrollHeight;
    }
  }, [messages]);

  const handleSendMessage = async () => {
    if (userInput.trim() === '') return;

    const newMessages = [...messages, { sender: 'user', text: userInput }];
    setMessages(newMessages);
    setUserInput('');
    setIsThinking(true);

    try {
      const startTime = Date.now();
      const response = await axios.post('http://127.0.0.1:8000/api/query', { 
        text: userInput,
        conversation: conversation
      });
      const endTime = Date.now();
      const responseTime = endTime - startTime;

      const botResponse = response.data.response;
      const logging = response.data.logging;
      
      const [textPart, htmlPart] = splitResponse(botResponse);
      
      const newMessagesWithResponseTime = [
        ...newMessages, 
        { sender: 'bot', text: textPart, responseTime, logging },
        ...(htmlPart ? [{ sender: 'bot', html: htmlPart, responseTime, logging }] : [])
      ];

      setMessages(newMessagesWithResponseTime);
      setConversation([...conversation, { role: 'human', content: userInput }, { role: 'ai', content: botResponse }]);
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

  const splitResponse = (response) => {
    const imgRegex = /<img[^>]+>/;
    const match = response.match(imgRegex);
    
    if (match) {
      const textPart = response.slice(0, match.index).trim();
      const htmlPart = match[0];
      return [textPart, htmlPart];
    }
    
    return [response, ''];
  };

  const handleServerResponse = (data) => {
    setMessages(prevMessages => [...prevMessages, { text: data.text, sender: 'bot' }]);
    if (data.image_path) {
      fetchAndRenderImage(data.image_path);
    }
  };

  const fetchAndRenderImage = async (path) => {
    try {
      // Use the path directly, as it's already relative to the public directory
      const response = await fetch(`/${path}`);
      const blob = await response.blob();
      const base64data = await blobToBase64(blob);
      setMessages(prevMessages => [
        ...prevMessages,
        { image: base64data, sender: 'bot' }
      ]);
    } catch (error) {
      console.error("Error fetching image:", error);
    }
  };

  const blobToBase64 = (blob) => {
    return new Promise((resolve, reject) => {
      const reader = new FileReader();
      reader.onloadend = () => resolve(reader.result);
      reader.onerror = reject;
      reader.readAsDataURL(blob);
    });
  };

  useEffect(() => {
    imagePaths.forEach(path => {
      fetchAndRenderImage(path);
    });
  }, [imagePaths]);

  const renderMessage = (message, index) => {
    return <Message message={message} index={index} />;
  };

  return (
    <div className="App">
      <header className="chat-header">
        <img src={process.env.PUBLIC_URL + '/logo.png'} alt="ToddGPT Logo" className="chat-logo" />
        <h1 className="chat-title">ToddGPT</h1>
      </header>
      <div className="chat-container" ref={chatContainerRef}>
        {messages.map((message, index) => renderMessage(message, index))}
        {isThinking && (
          <div className="message-container bot">
            <div className="chat-message bot thinking">
              <div className="message-text thinking">Thinking...</div>
            </div>
          </div>
        )}
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
