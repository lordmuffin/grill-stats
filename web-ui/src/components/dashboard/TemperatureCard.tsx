import { useEffect, useState, useRef } from 'react';
import { useTranslation } from 'react-i18next';
import {
  Box,
  Card,
  CardContent,
  Typography,
  CircularProgress,
  Chip,
  LinearProgress,
  Stack,
  Tooltip,
  IconButton,
  CardActionArea,
  CardActions,
  Badge,
  Divider,
  Paper,
  Fade,
  useTheme,
} from '@mui/material';
import BatteryFullIcon from '@mui/icons-material/BatteryFull';
import BatteryAlertIcon from '@mui/icons-material/BatteryAlert';
import Battery60Icon from '@mui/icons-material/Battery60';
import SignalCellularAltIcon from '@mui/icons-material/SignalCellularAlt';
import SignalCellularConnectedNoInternet0BarIcon from '@mui/icons-material/SignalCellularConnectedNoInternet0Bar';
import SignalCellular4BarIcon from '@mui/icons-material/SignalCellular4Bar';
import SignalCellular1BarIcon from '@mui/icons-material/SignalCellular1Bar';
import ThermostatIcon from '@mui/icons-material/Thermostat';
import AccessTimeIcon from '@mui/icons-material/AccessTime';
import RefreshIcon from '@mui/icons-material/Refresh';
import ArrowUpwardIcon from '@mui/icons-material/ArrowUpward';
import ArrowDownwardIcon from '@mui/icons-material/ArrowDownward';
import MoreVertIcon from '@mui/icons-material/MoreVert';
import { useAppSelector } from '@/hooks/reduxHooks';
import { selectTemperatureUnit } from '@/store/slices/temperatureSlice';
import useTemperatureUnit from '@/hooks/useTemperatureUnit';
import useTemperatureSocket from '@/hooks/useTemperatureSocket';
import { api } from '@/store/api';
import { formatDistanceToNow } from 'date-fns';
import type { Probe } from '@/types';

interface TemperatureCardProps {
  deviceId: string;
  probeId?: string;
  probe?: Probe;
}

/**
 * Enhanced card that displays current temperature information for a device/probe
 * with real-time updates, trend indicators, and improved visualization
 */
const TemperatureCard = ({ deviceId, probeId, probe }: TemperatureCardProps) => {
  const { t } = useTranslation();
  const theme = useTheme();
  const { formatTemperature, getUnitSymbol } = useTemperatureUnit();
  const temperatureUnit = useAppSelector(selectTemperatureUnit);
  const [lastUpdate, setLastUpdate] = useState<Date | null>(null);
  const [prevTemperature, setPrevTemperature] = useState<number | null>(null);
  const [trend, setTrend] = useState<'up' | 'down' | 'stable'>('stable');
  const [trendAmount, setTrendAmount] = useState<number>(0);
  const [isUpdating, setIsUpdating] = useState<boolean>(false);
  const [animateIn, setAnimateIn] = useState<boolean>(false);
  const cardRef = useRef<HTMLDivElement>(null);
  
  // Animation effect on mount
  useEffect(() => {
    setAnimateIn(true);
  }, []);
  
  // Set up real-time socket
  const { connected } = useTemperatureSocket(deviceId, probeId);
  
  // Fetch current temperature data
  const { 
    data: tempData, 
    isLoading, 
    error, 
    refetch 
  } = api.useGetCurrentTemperatureQuery({ 
    deviceId,
    probeId, 
  }, {
    pollingInterval: 30000, // Poll every 30 seconds as backup for websocket
  });
  
  // Track previous temperature to show trends
  useEffect(() => {
    if (tempData?.data.temperature !== undefined) {
      const currentTemp = tempData.data.temperature;
      
      if (prevTemperature !== null) {
        // Calculate trend
        if (currentTemp > prevTemperature) {
          setTrend('up');
          setTrendAmount(currentTemp - prevTemperature);
        } else if (currentTemp < prevTemperature) {
          setTrend('down');
          setTrendAmount(prevTemperature - currentTemp);
        } else {
          setTrend('stable');
          setTrendAmount(0);
        }
      }
      
      setPrevTemperature(currentTemp);
    }
  }, [tempData?.data.temperature]);
  
  // Update last update time
  useEffect(() => {
    if (tempData?.data.timestamp) {
      setLastUpdate(new Date(tempData.data.timestamp));
    }
  }, [tempData]);
  
  // Helper functions for rendering indicators
  const getBatteryIcon = (level?: number) => {
    if (!level || level < 20) {
      return <BatteryAlertIcon color="error" />;
    } else if (level < 60) {
      return <Battery60Icon color="warning" />;
    }
    return <BatteryFullIcon color="success" />;
  };
  
  const getSignalIcon = (strength?: number) => {
    if (!strength || strength < 20) {
      return <SignalCellularConnectedNoInternet0BarIcon color="error" />;
    } else if (strength < 60) {
      return <SignalCellular1BarIcon color="warning" />;
    }
    return <SignalCellular4BarIcon color="success" />;
  };
  
  // Handle manual refresh
  const handleRefresh = () => {
    setIsUpdating(true);
    refetch().finally(() => {
      setTimeout(() => setIsUpdating(false), 500);
    });
  };
  
  // Temperature styling based on value
  const getTemperatureColor = (temp: number) => {
    // Adjust for temperature unit
    const adjustedTemp = temperatureUnit === 'C' 
      ? temp 
      : (temp - 32) * 5/9; // Convert F to C for consistent coloring
    
    if (adjustedTemp < 0) return 'rgb(0, 100, 255)';  // Cold
    if (adjustedTemp < 40) return 'rgb(30, 144, 255)'; // Cool
    if (adjustedTemp < 70) return 'rgb(255, 165, 0)';  // Warm
    if (adjustedTemp < 100) return 'rgb(255, 69, 0)';  // Hot
    return 'rgb(200, 0, 0)'; // Very hot
  };
  
  // Get name to display
  const getName = () => {
    if (probe) {
      return probe.name || `Probe ${probe.probeId}`;
    }
    
    return 'All Probes';
  };
  
  if (isLoading) {
    return (
      <Fade in={animateIn} timeout={800}>
        <Card 
          sx={{ 
            minWidth: 300, 
            height: '100%',
            borderRadius: 3,
            boxShadow: theme.palette.mode === 'dark'
              ? '0 4px 20px rgba(0, 0, 0, 0.2)'
              : '0 4px 20px rgba(0, 0, 0, 0.05)',
          }}
        >
          <CardContent sx={{ 
            display: 'flex', 
            flexDirection: 'column',
            justifyContent: 'center',
            alignItems: 'center',
            height: '100%',
            py: 4
          }}>
            <CircularProgress size={40} />
            <Typography sx={{ mt: 3 }} variant="body1">
              {t('loading.chart')}
            </Typography>
          </CardContent>
        </Card>
      </Fade>
    );
  }
  
  if (error || !tempData) {
    return (
      <Fade in={animateIn} timeout={800}>
        <Card 
          sx={{ 
            minWidth: 300, 
            height: '100%',
            borderRadius: 3,
            boxShadow: theme.palette.mode === 'dark'
              ? '0 4px 20px rgba(0, 0, 0, 0.2)'
              : '0 4px 20px rgba(0, 0, 0, 0.05)',
            overflow: 'hidden',
            position: 'relative',
            '&::before': {
              content: '""',
              position: 'absolute',
              top: 0,
              left: 0,
              width: '100%',
              height: '4px',
              backgroundColor: 'error.main',
            },
          }}
        >
          <CardContent sx={{ pt: 4 }}>
            <Typography variant="h6" color="error" gutterBottom>
              {t('error.loadingChart')}
            </Typography>
            
            <Typography variant="body2" color="text.secondary" paragraph>
              {t('error.loadingData')}
            </Typography>
            
            <Button 
              startIcon={<RefreshIcon />}
              variant="outlined"
              color="primary"
              onClick={handleRefresh}
              size="small"
              sx={{ mt: 1 }}
            >
              {t('button.refresh')}
            </Button>
          </CardContent>
        </Card>
      </Fade>
    );
  }
  
  const temperature = tempData.data.temperature;
  const batteryLevel = tempData.data.batteryLevel;
  const signalStrength = tempData.data.signalStrength;
  const timestamp = tempData.data.timestamp;
  
  return (
    <Fade in={animateIn} timeout={800}>
      <Card 
        ref={cardRef}
        sx={{ 
          minWidth: 300,
          height: '100%',
          display: 'flex',
          flexDirection: 'column',
          borderRadius: 3,
          position: 'relative',
          overflow: 'hidden',
          boxShadow: theme.palette.mode === 'dark'
            ? '0 4px 20px rgba(0, 0, 0, 0.25)'
            : '0 4px 20px rgba(0, 0, 0, 0.07)',
          transition: 'transform 0.2s, box-shadow 0.2s',
          '&:hover': {
            transform: 'translateY(-4px)',
            boxShadow: theme.palette.mode === 'dark'
              ? '0 8px 30px rgba(0, 0, 0, 0.3)'
              : '0 8px 30px rgba(0, 0, 0, 0.1)',
          },
          '&::before': {
            content: '""',
            position: 'absolute',
            top: 0,
            left: 0,
            width: '100%',
            height: '4px',
            backgroundColor: getTemperatureColor(temperature),
          },
        }}
      >
        <CardContent sx={{ flexGrow: 1, position: 'relative', p: 3 }}>
          {/* Header */}
          <Box sx={{ 
            display: 'flex', 
            justifyContent: 'space-between', 
            alignItems: 'flex-start',
            mb: 2 
          }}>
            <Box>
              <Typography 
                variant="h6" 
                component="div" 
                fontWeight="medium"
                gutterBottom
              >
                {getName()}
              </Typography>
              
              <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mt: 0.5 }}>
                <Chip 
                  icon={<ThermostatIcon />}
                  label={connected ? t('status.online') : t('status.offline')}
                  color={connected ? 'success' : 'default'}
                  size="small"
                  sx={{ 
                    borderRadius: 1,
                    height: 24,
                    '& .MuiChip-label': { px: 1 },
                    '& .MuiChip-icon': { fontSize: '0.9rem' }
                  }}
                />
                
                {isUpdating && (
                  <CircularProgress size={16} sx={{ ml: 1 }} />
                )}
              </Box>
            </Box>
            
            <Box>
              <IconButton 
                size="small" 
                onClick={handleRefresh} 
                sx={{ 
                  mb: 1,
                  opacity: 0.7,
                  '&:hover': { opacity: 1 }
                }}
              >
                <RefreshIcon fontSize="small" />
              </IconButton>
            </Box>
          </Box>
          
          {/* Temperature Display */}
          <Box 
            sx={{ 
              display: 'flex', 
              flexDirection: 'column',
              alignItems: 'center', 
              justifyContent: 'center',
              py: 2,
              position: 'relative'
            }}
          >
            <Typography 
              variant="h2" 
              component="div"
              sx={{ 
                fontWeight: 'bold',
                color: getTemperatureColor(temperature),
                textShadow: theme.palette.mode === 'dark' 
                  ? '0 2px 10px rgba(0, 0, 0, 0.3)'
                  : '0 2px 10px rgba(0, 0, 0, 0.1)',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
              }}
            >
              {formatTemperature(temperature)}
              
              {/* Trend indicator */}
              {trend !== 'stable' && (
                <Box 
                  sx={{ 
                    display: 'flex',
                    flexDirection: 'column',
                    alignItems: 'flex-start',
                    ml: 1.5,
                    mt: 1
                  }}
                >
                  <Tooltip 
                    title={`${trend === 'up' ? 'Increased' : 'Decreased'} by ${trendAmount.toFixed(1)}°${temperatureUnit}`} 
                    arrow
                  >
                    <Box sx={{ 
                      display: 'flex', 
                      alignItems: 'center',
                      color: trend === 'up' ? 'error.main' : 'info.main'
                    }}>
                      {trend === 'up' ? (
                        <ArrowUpwardIcon fontSize="small" color="error" />
                      ) : (
                        <ArrowDownwardIcon fontSize="small" color="info" />
                      )}
                      <Typography 
                        variant="caption" 
                        fontWeight="bold"
                        color={trend === 'up' ? 'error.main' : 'info.main'}
                        sx={{ ml: 0.3 }}
                      >
                        {trendAmount.toFixed(1)}°
                      </Typography>
                    </Box>
                  </Tooltip>
                </Box>
              )}
            </Typography>
          </Box>
          
          {/* Status Indicators */}
          <Paper 
            elevation={0}
            sx={{ 
              p: 2, 
              mt: 2, 
              borderRadius: 2,
              backgroundColor: theme.palette.mode === 'dark' 
                ? 'rgba(30, 30, 30, 0.5)' 
                : 'rgba(245, 245, 245, 0.5)',
            }}
          >
            <Stack spacing={1.5}>
              {/* Battery Level */}
              <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.5 }}>
                <Tooltip title={`${t('devices.batteryLevel')}: ${batteryLevel || 0}%`} arrow>
                  <Box sx={{ minWidth: 24, display: 'flex', justifyContent: 'center' }}>
                    {getBatteryIcon(batteryLevel)}
                  </Box>
                </Tooltip>
                <Box sx={{ flexGrow: 1 }}>
                  <LinearProgress 
                    variant="determinate" 
                    value={batteryLevel || 0}
                    color={
                      !batteryLevel || batteryLevel < 20 ? 'error' :
                      batteryLevel < 60 ? 'warning' : 'success'
                    }
                    sx={{ 
                      height: 8, 
                      borderRadius: 2,
                      backgroundColor: theme.palette.mode === 'dark' 
                        ? 'rgba(255, 255, 255, 0.1)' 
                        : 'rgba(0, 0, 0, 0.08)',
                    }}
                  />
                </Box>
                <Typography variant="body2" fontWeight="medium">
                  {batteryLevel || 0}%
                </Typography>
              </Box>
              
              {/* Signal Strength */}
              <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.5 }}>
                <Tooltip title={`${t('devices.signalStrength')}: ${signalStrength || 0}%`} arrow>
                  <Box sx={{ minWidth: 24, display: 'flex', justifyContent: 'center' }}>
                    {getSignalIcon(signalStrength)}
                  </Box>
                </Tooltip>
                <Box sx={{ flexGrow: 1 }}>
                  <LinearProgress 
                    variant="determinate" 
                    value={signalStrength || 0}
                    color={
                      !signalStrength || signalStrength < 20 ? 'error' :
                      signalStrength < 60 ? 'warning' : 'success'
                    }
                    sx={{ 
                      height: 8, 
                      borderRadius: 2,
                      backgroundColor: theme.palette.mode === 'dark' 
                        ? 'rgba(255, 255, 255, 0.1)' 
                        : 'rgba(0, 0, 0, 0.08)',
                    }}
                  />
                </Box>
                <Typography variant="body2" fontWeight="medium">
                  {signalStrength || 0}%
                </Typography>
              </Box>
            </Stack>
          </Paper>
        </CardContent>
        
        {/* Last Updated */}
        <CardActions
          sx={{ 
            px: 2,
            py: 1.5,
            borderTop: '1px solid',
            borderColor: 'divider',
            bgcolor: theme.palette.mode === 'dark' 
              ? 'rgba(0, 0, 0, 0.2)' 
              : 'rgba(0, 0, 0, 0.03)',
            display: 'flex',
            justifyContent: 'space-between',
          }}
        >
          <Box sx={{ display: 'flex', alignItems: 'center' }}>
            <AccessTimeIcon 
              fontSize="small" 
              sx={{ mr: 1, opacity: 0.7, color: 'text.secondary' }} 
            />
            <Typography variant="body2" color="text.secondary">
              {timestamp ? (
                formatDistanceToNow(new Date(timestamp), { addSuffix: true })
              ) : (
                t('dashboard.noData')
              )}
            </Typography>
          </Box>
          
          <Box>
            {connected && (
              <Badge 
                variant="dot" 
                color="success"
                overlap="circular"
                sx={{ 
                  '& .MuiBadge-badge': {
                    animation: 'pulse 2s infinite',
                    '@keyframes pulse': {
                      '0%': {
                        transform: 'scale(.8)',
                        opacity: 1
                      },
                      '50%': {
                        transform: 'scale(1)',
                        opacity: 0.7
                      },
                      '100%': {
                        transform: 'scale(.8)',
                        opacity: 1
                      }
                    }
                  }
                }}
              >
                <Box sx={{ width: 8, height: 8 }} />
              </Badge>
            )}
          </Box>
        </CardActions>
      </Card>
    </Fade>
  );
};

export default TemperatureCard;