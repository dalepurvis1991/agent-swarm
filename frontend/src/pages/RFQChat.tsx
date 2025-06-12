import React, { useState, useEffect } from 'react';
import { Box, TextField, Button, Typography, Paper, CircularProgress } from '@mui/material';
import axios from 'axios';

interface Message {
  type: 'user' | 'agent';
  content: string;
}

const RFQChat: React.FC = () => {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState('');
  const [sessionId, setSessionId] = useState<number | null>(null);
  const [loading, setLoading] = useState(false);
  const [status, setStatus] = useState<'pending' | 'complete'>('pending');

  const handleStart = async () => {
    if (!input.trim()) return;
    
    setLoading(true);
    try {
      const response = await axios.post('/api/rfq/start', { spec: input });
      setSessionId(response.data.session_id);
      setMessages([
        { type: 'user', content: input },
        { type: 'agent', content: response.data.question }
      ]);
      setStatus(response.data.status);
      setInput('');
    } catch (error) {
      console.error('Error starting RFQ:', error);
    } finally {
      setLoading(false);
    }
  };

  const handleAnswer = async () => {
    if (!input.trim() || !sessionId) return;
    
    setLoading(true);
    try {
      const response = await axios.post('/api/rfq/answer', {
        session_id: sessionId,
        answer: input
      });
      
      setMessages(prev => [
        ...prev,
        { type: 'user', content: input },
        { type: 'agent', content: response.data.question || 'Specification complete!' }
      ]);
      
      setStatus(response.data.status);
      setInput('');
    } catch (error) {
      console.error('Error answering RFQ:', error);
    } finally {
      setLoading(false);
    }
  };

  return (
    <Box sx={{ maxWidth: 600, mx: 'auto', p: 3 }}>
      <Typography variant="h4" gutterBottom>
        RFQ Specification Chat
      </Typography>
      
      <Paper sx={{ p: 2, mb: 2, maxHeight: 400, overflow: 'auto' }}>
        {messages.map((msg, idx) => (
          <Box
            key={idx}
            sx={{
              mb: 2,
              p: 1,
              borderRadius: 1,
              bgcolor: msg.type === 'user' ? 'primary.light' : 'grey.100',
              alignSelf: msg.type === 'user' ? 'flex-end' : 'flex-start',
            }}
          >
            <Typography>{msg.content}</Typography>
          </Box>
        ))}
      </Paper>

      {status === 'complete' && (
        <Typography color="success.main" sx={{ mb: 2 }}>
          Specification complete! You can now proceed with the quote.
        </Typography>
      )}

      <Box sx={{ display: 'flex', gap: 1 }}>
        <TextField
          fullWidth
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder={sessionId ? "Type your answer..." : "Enter your specification..."}
          disabled={loading || status === 'complete'}
        />
        <Button
          variant="contained"
          onClick={sessionId ? handleAnswer : handleStart}
          disabled={loading || !input.trim() || status === 'complete'}
        >
          {loading ? <CircularProgress size={24} /> : sessionId ? 'Send' : 'Start'}
        </Button>
      </Box>
    </Box>
  );
};

export default RFQChat; 