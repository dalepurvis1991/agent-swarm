import { useState, useEffect, useRef } from 'react';

interface WebSocketHook {
  lastMessage: WebSocketMessage | null;
  sendMessage: (message: string) => void;
  isConnected: boolean;
}

interface WebSocketMessage {
  data: string;
  timestamp: number;
}

export const useWebSocket = (url: string): WebSocketHook => {
  const [lastMessage, setLastMessage] = useState<WebSocketMessage | null>(null);
  const [isConnected, setIsConnected] = useState(false);
  const ws = useRef<WebSocket | null>(null);
  
  useEffect(() => {
    // Create WebSocket connection
    ws.current = new WebSocket(url);
    
    // Connection opened
    ws.current.onopen = () => {
      console.log('WebSocket connected');
      setIsConnected(true);
    };
    
    // Listen for messages
    ws.current.onmessage = (event) => {
      setLastMessage({
        data: event.data,
        timestamp: Date.now()
      });
    };
    
    // Connection closed
    ws.current.onclose = () => {
      console.log('WebSocket disconnected');
      setIsConnected(false);
    };
    
    // Connection error
    ws.current.onerror = (error) => {
      console.error('WebSocket error:', error);
      setIsConnected(false);
    };
    
    // Cleanup on unmount
    return () => {
      if (ws.current) {
        ws.current.close();
      }
    };
  }, [url]);
  
  const sendMessage = (message: string) => {
    if (ws.current && ws.current.readyState === WebSocket.OPEN) {
      ws.current.send(message);
    } else {
      console.warn('WebSocket is not connected');
    }
  };
  
  return {
    lastMessage,
    sendMessage,
    isConnected
  };
}; 