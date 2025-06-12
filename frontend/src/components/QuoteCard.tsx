import React, { useState } from 'react';
import {
  Card,
  CardContent,
  Typography,
  Button,
  Box,
  CircularProgress,
  Chip
} from '@mui/material';
import { useNotification } from '../contexts/NotificationContext';
import axios from 'axios';

interface QuoteCardProps {
  offer: {
    id: number;
    supplier: string;
    price: number;
    status: string;
    product_name: string;
    specification: string;
  };
  onStatusChange: () => void;
}

const QuoteCard: React.FC<QuoteCardProps> = ({ offer, onStatusChange }) => {
  const [loading, setLoading] = useState(false);
  const { showNotification } = useNotification();
  
  const handleAccept = async () => {
    setLoading(true);
    try {
      const response = await axios.post(`/api/offers/${offer.id}/accept`);
      
      showNotification({
        title: 'Purchase Order Sent',
        message: `PO ${response.data.po_number} has been sent to ${offer.supplier}`,
        type: 'success'
      });
      
      onStatusChange();
    } catch (error) {
      showNotification({
        title: 'Error',
        message: 'Failed to send purchase order',
        type: 'error'
      });
    } finally {
      setLoading(false);
    }
  };
  
  const getStatusColor = (status: string) => {
    switch (status) {
      case 'open':
        return 'default';
      case 'countered':
        return 'warning';
      case 'final':
        return 'info';
      case 'needs_user':
        return 'error';
      case 'ordered':
        return 'success';
      default:
        return 'default';
    }
  };
  
  return (
    <Card sx={{ mb: 2 }}>
      <CardContent>
        <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: 2 }}>
          <Typography variant="h6">{offer.supplier}</Typography>
          <Chip
            label={offer.status.toUpperCase()}
            color={getStatusColor(offer.status)}
            size="small"
          />
        </Box>
        
        <Typography variant="body1" gutterBottom>
          {offer.product_name}
        </Typography>
        
        <Typography variant="body2" color="text.secondary" gutterBottom>
          {offer.specification}
        </Typography>
        
        <Typography variant="h5" color="primary" gutterBottom>
          ${offer.price.toFixed(2)}
        </Typography>
        
        {offer.status === 'final' && (
          <Button
            variant="contained"
            color="primary"
            onClick={handleAccept}
            disabled={loading}
            fullWidth
          >
            {loading ? (
              <CircularProgress size={24} color="inherit" />
            ) : (
              'Accept & Send PO'
            )}
          </Button>
        )}
      </CardContent>
    </Card>
  );
};

export default QuoteCard; 