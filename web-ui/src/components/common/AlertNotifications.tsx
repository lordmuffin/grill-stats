import { useEffect, useState, useMemo } from 'react';
import { useTranslation } from 'react-i18next';
import { 
  Alert, 
  AlertTitle, 
  Snackbar, 
  Stack, 
  IconButton, 
  Typography,
  Box,
  Collapse,
  Grow,
  Slide,
  Fade,
  Paper,
  useTheme,
  alpha,
  useMediaQuery,
  LinearProgress,
  Button
} from '@mui/material';
import CloseIcon from '@mui/icons-material/Close';
import CheckCircleOutlineIcon from '@mui/icons-material/CheckCircleOutline';
import ErrorOutlineIcon from '@mui/icons-material/ErrorOutline';
import WarningAmberIcon from '@mui/icons-material/WarningAmber';
import InfoOutlinedIcon from '@mui/icons-material/InfoOutlined';
import { useAppSelector, useAppDispatch } from '@/hooks/reduxHooks';
import { selectAlerts, removeAlert } from '@/store/slices/uiSlice';
import { motion, AnimatePresence } from 'framer-motion';
import type { AlertNotification } from '@/types';

/**
 * Single alert notification item with custom styling and animation
 */
interface AlertNotificationItemProps {
  alert: AlertNotification;
  onClose: (id: string) => void;
  isExiting: boolean;
}

interface AlertWithCount extends AlertNotification {
  count?: number;
}

const AlertNotificationItem = ({ alert, onClose, isExiting }: AlertNotificationItemProps) => {
  const alertWithCount = alert as AlertWithCount;
  const { t } = useTranslation();
  const theme = useTheme();
  
  // Get alert icon based on type
  const getAlertIcon = (type: 'success' | 'error' | 'warning' | 'info') => {
    switch (type) {
      case 'success':
        return <CheckCircleOutlineIcon fontSize="small" />;
      case 'error':
        return <ErrorOutlineIcon fontSize="small" />;
      case 'warning':
        return <WarningAmberIcon fontSize="small" />;
      case 'info':
        return <InfoOutlinedIcon fontSize="small" />;
      default:
        return <InfoOutlinedIcon fontSize="small" />;
    }
  };
  
  // Get style based on alert type
  const getAlertStyle = (type: 'success' | 'error' | 'warning' | 'info') => {
    const colors = {
      success: theme.palette.success.main,
      error: theme.palette.error.main,
      warning: theme.palette.warning.main,
      info: theme.palette.info.main,
    };
    
    return {
      backgroundColor: theme.palette.mode === 'dark' 
        ? alpha(colors[type], 0.15)
        : alpha(colors[type], 0.08),
      borderLeft: `4px solid ${colors[type]}`,
      color: theme.palette.getContrastText(theme.palette.background.paper),
    };
  };

  return (
    <Paper
      elevation={3}
      sx={{
        width: '100%',
        borderRadius: 2,
        overflow: 'hidden',
        ...getAlertStyle(alert.type),
        boxShadow: theme.shadows[4],
        transition: 'all 0.2s ease',
        '&:hover': {
          boxShadow: theme.shadows[8],
          transform: 'translateY(-2px)'
        }
      }}
    >
      <Box sx={{ 
        display: 'flex',
        alignItems: 'flex-start',
        p: 2
      }}>
        <Box 
          sx={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            mr: 2,
            mt: 0.5,
            position: 'relative'
          }}
        >
          <Box sx={{ color: `${alert.type}.main` }}>
            {getAlertIcon(alert.type)}
          </Box>
          
          {/* Show count badge if this alert represents multiple grouped alerts */}
          {alertWithCount.count && alertWithCount.count > 1 && (
            <Badge
              badgeContent={alertWithCount.count > 99 ? '99+' : alertWithCount.count}
              color={alert.type === 'error' ? 'error' : alert.type === 'warning' ? 'warning' : 'primary'}
              sx={{ 
                position: 'absolute',
                top: -8,
                right: -10,
                '& .MuiBadge-badge': {
                  fontSize: '0.65rem',
                  height: 16,
                  minWidth: 16,
                  padding: '0 4px'
                }
              }}
            />
          )}
        </Box>
        
        <Box sx={{ flexGrow: 1 }}>
          <Typography 
            variant="subtitle1" 
            component="div" 
            fontWeight="bold"
            sx={{
              color: `${alert.type}.main`,
              mb: 0.5
            }}
          >
            {t(`alerts.${alert.type}`) || alert.type.charAt(0).toUpperCase() + alert.type.slice(1)}
          </Typography>
          
          <Typography 
            variant="body2" 
            sx={{ 
              wordBreak: 'break-word',
              whiteSpace: 'pre-wrap'
            }}
          >
            {alert.message}
          </Typography>
        </Box>
        
        <IconButton 
          size="small" 
          onClick={() => onClose(alert.id)}
          sx={{ 
            ml: 1, 
            mt: -0.5, 
            opacity: 0.6,
            '&:hover': { opacity: 1 }
          }}
        >
          <CloseIcon fontSize="small" />
        </IconButton>
      </Box>
      
      {alert.autoHide && alert.duration && (
        <Box sx={{ px: 0 }}>
          <LinearProgress 
            variant="determinate" 
            value={0} 
            sx={{
              height: 2,
              '& .MuiLinearProgress-bar': {
                animation: `progress ${alert.duration}ms linear`,
                '@keyframes progress': {
                  '0%': { transform: 'translateX(-100%)' },
                  '100%': { transform: 'translateX(0)' }
                }
              }
            }}
          />
        </Box>
      )}
    </Paper>
  );
};

/**
 * Enhanced component for displaying alert notifications with custom styling,
 * animations, and better user experience
 */
const AlertNotifications = () => {
  const { t } = useTranslation();
  const theme = useTheme();
  const isMobile = useMediaQuery(theme.breakpoints.down('sm'));
  const dispatch = useAppDispatch();
  const rawAlerts = useAppSelector(selectAlerts);
  const [exiting, setExiting] = useState<string | null>(null);
  
  // Process alerts to group similar ones
  const alerts = useMemo(() => {
    const alertMap = new Map<string, AlertWithCount>();
    
    // Group alerts by type and message
    rawAlerts.forEach(alert => {
      const key = `${alert.type}-${alert.message}`;
      
      if (alertMap.has(key)) {
        const existing = alertMap.get(key)!;
        existing.count = (existing.count || 1) + 1;
      } else {
        alertMap.set(key, { ...alert, count: 1 });
      }
    });
    
    // Convert map back to array
    return Array.from(alertMap.values());
  }, [rawAlerts]);
  
  // Set up auto-hide timeouts for alerts
  useEffect(() => {
    const timeouts: NodeJS.Timeout[] = [];
    
    alerts.forEach((alert) => {
      if (alert.autoHide && alert.duration) {
        const timeout = setTimeout(() => {
          handleCloseWithAnimation(alert.id);
        }, alert.duration);
        
        timeouts.push(timeout);
      }
    });
    
    // Clean up timeouts on unmount
    return () => {
      timeouts.forEach(clearTimeout);
    };
  }, [alerts, dispatch]);
  
  // Handle close with exit animation
  const handleCloseWithAnimation = (id: string) => {
    setExiting(id);
    // Allow time for exit animation before removing from state
    setTimeout(() => {
      dispatch(removeAlert(id));
      setExiting(null);
    }, 300);
  };
  
  // Clear all alerts with animation
  const handleClearAll = () => {
    // Set all alerts as exiting
    alerts.forEach(alert => {
      setExiting(alert.id);
    });
    
    // Clear after animation completes
    setTimeout(() => {
      dispatch({ type: 'ui/clearAlerts' });
      setExiting(null);
    }, 300);
  };
  
  // Animation variants for framer-motion
  const alertVariants = {
    initial: { opacity: 0, y: 50, scale: 0.8 },
    animate: { opacity: 1, y: 0, scale: 1, transition: { duration: 0.3 } },
    exit: { opacity: 0, x: 100, transition: { duration: 0.2 } }
  };
  
  return (
    <Box
      sx={{
        position: 'fixed',
        bottom: isMobile ? 16 : 24,
        right: isMobile ? 16 : 24,
        zIndex: 2000,
        maxWidth: isMobile ? '95%' : 400,
      }}
    >
      {/* Clear all button when multiple alerts */}
      {alerts.length > 1 && (
        <motion.div
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.2 }}
        >
          <Box 
            sx={{ 
              display: 'flex', 
              justifyContent: 'flex-end',
              mb: 1.5,
            }}
          >
            <Button
              size="small"
              variant="text"
              color="inherit"
              startIcon={<CloseIcon fontSize="small" />}
              onClick={handleClearAll}
              sx={{ 
                backgroundColor: theme.palette.mode === 'dark' 
                  ? alpha(theme.palette.background.paper, 0.6)
                  : alpha(theme.palette.background.paper, 0.8),
                backdropFilter: 'blur(4px)',
                borderRadius: 1.5,
                fontSize: '0.75rem',
                px: 1,
                py: 0.5,
                '&:hover': {
                  backgroundColor: theme.palette.mode === 'dark'
                    ? alpha(theme.palette.background.paper, 0.8)
                    : alpha(theme.palette.background.paper, 0.95),
                }
              }}
            >
              {t('alerts.clearAll')}
            </Button>
          </Box>
        </motion.div>
      )}
      
      <Stack
        spacing={1.5}
        sx={{
          maxHeight: '80vh',
          overflowY: 'auto',
          overflowX: 'hidden',
          // Hide scrollbar for clean look
          '&::-webkit-scrollbar': { display: 'none' },
          msOverflowStyle: 'none',
          scrollbarWidth: 'none',
        }}
      >
        <AnimatePresence>
          {alerts.map((alert) => (
          <motion.div
            key={alert.id}
            layout
            initial="initial"
            animate="animate"
            exit="exit"
            variants={alertVariants}
            style={{
              marginBottom: 8, 
              opacity: exiting === alert.id ? 0.5 : 1,
              transform: exiting === alert.id ? 'translateX(30px)' : 'translateX(0)',
              transition: 'all 0.3s ease'
            }}
          >
            <AlertNotificationItem 
              alert={alert} 
              onClose={handleCloseWithAnimation} 
              isExiting={exiting === alert.id}
            />
          </motion.div>
        ))}
        </AnimatePresence>
      </Stack>
    </Box>
  );
};

export default AlertNotifications;