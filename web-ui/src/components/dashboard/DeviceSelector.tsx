import { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { 
  Box, 
  FormControl, 
  InputLabel, 
  MenuItem, 
  Select, 
  SelectChangeEvent,
  Typography,
  Button,
  CircularProgress,
  Paper,
  Chip,
  Fade,
  IconButton,
  Tooltip,
  Badge,
  useTheme,
  Autocomplete,
  TextField,
  Avatar
} from '@mui/material';
import AddIcon from '@mui/icons-material/Add';
import DeviceThermostatIcon from '@mui/icons-material/DeviceThermostat';
import SensorsIcon from '@mui/icons-material/Sensors';
import RefreshIcon from '@mui/icons-material/Refresh';
import BatteryFullIcon from '@mui/icons-material/BatteryFull';
import BatteryChargingFullIcon from '@mui/icons-material/BatteryChargingFull';
import Battery60Icon from '@mui/icons-material/Battery60';
import Battery20Icon from '@mui/icons-material/Battery20';
import SignalCellularAltIcon from '@mui/icons-material/SignalCellularAlt';
import { useAppDispatch, useAppSelector } from '@/hooks/reduxHooks';
import { setSelectedDevice, setSelectedProbe, openDeviceDiscovery } from '@/store/slices/deviceSlice';
import { selectSelectedDevice, selectSelectedProbe } from '@/store/slices/deviceSlice';
import { api } from '@/store/api';
import type { Device, Probe } from '@/types';

/**
 * Enhanced component for selecting a device and probe with improved UI
 */
const DeviceSelector = () => {
  const { t } = useTranslation();
  const theme = useTheme();
  const dispatch = useAppDispatch();
  const selectedDeviceId = useAppSelector(selectSelectedDevice);
  const selectedProbeId = useAppSelector(selectSelectedProbe);
  
  const [animateIn, setAnimateIn] = useState(false);
  
  // Animation effect
  useEffect(() => {
    setAnimateIn(true);
  }, []);
  
  // Fetch devices
  const { data: devicesResponse, isLoading, error, refetch } = api.useGetDevicesQuery({ status: 'online' });
  const devices = devicesResponse?.data.devices || [];
  
  // Find the selected device
  const selectedDevice = devices.find(device => device.id === selectedDeviceId);
  
  // Get probes for the selected device
  const probes: Probe[] = selectedDevice?.probes || [];
  
  // Auto-select the first device if none is selected
  useEffect(() => {
    if (devices.length > 0 && !selectedDeviceId) {
      dispatch(setSelectedDevice(devices[0].id));
    }
  }, [devices, selectedDeviceId, dispatch]);
  
  // Get battery level icon based on percentage
  const getBatteryIcon = (batteryLevel: number) => {
    if (batteryLevel > 80) {
      return <BatteryFullIcon color="success" />;
    } else if (batteryLevel > 40) {
      return <Battery60Icon color="warning" />;
    } else {
      return <Battery20Icon color="error" />;
    }
  };
  
  // Handle device selection
  const handleDeviceChange = (event: SelectChangeEvent<string>) => {
    const deviceId = event.target.value;
    dispatch(setSelectedDevice(deviceId));
    // Reset probe selection when changing devices
    dispatch(setSelectedProbe(null));
  };
  
  // Handle probe selection
  const handleProbeChange = (event: SelectChangeEvent<string>) => {
    const probeId = event.target.value;
    dispatch(setSelectedProbe(probeId || null));
  };
  
  // Open device discovery wizard
  const handleAddDevice = () => {
    dispatch(openDeviceDiscovery());
  };
  
  // Handle refresh
  const handleRefresh = () => {
    refetch();
  };
  
  if (isLoading) {
    return (
      <Paper 
        elevation={0}
        sx={{ 
          p: 3, 
          display: 'flex', 
          alignItems: 'center', 
          justifyContent: 'center',
          borderRadius: 2,
          backgroundColor: theme.palette.mode === 'dark' 
            ? 'rgba(30, 30, 30, 0.5)' 
            : 'rgba(245, 245, 245, 0.5)'
        }}
      >
        <CircularProgress size={24} sx={{ mr: 2 }} />
        <Typography variant="body1">
          {t('loading.devices')}
        </Typography>
      </Paper>
    );
  }
  
  if (error) {
    return (
      <Paper 
        elevation={1}
        sx={{ 
          p: 3, 
          borderRadius: 2,
          backgroundColor: theme.palette.mode === 'dark' 
            ? 'rgba(211, 47, 47, 0.15)' 
            : 'rgba(211, 47, 47, 0.08)',
          border: '1px solid',
          borderColor: 'error.main',
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          gap: 2
        }}
      >
        <Typography color="error">
          {t('error.loadingData')}
        </Typography>
        <Button 
          variant="outlined" 
          color="error" 
          onClick={handleRefresh}
          startIcon={<RefreshIcon />}
        >
          {t('button.refresh')}
        </Button>
      </Paper>
    );
  }
  
  if (devices.length === 0) {
    return (
      <Fade in={animateIn} timeout={800}>
        <Paper 
          elevation={1}
          sx={{ 
            p: 4, 
            display: 'flex', 
            flexDirection: 'column', 
            alignItems: 'center',
            gap: 3,
            borderRadius: 2,
            border: '1px solid',
            borderColor: theme.palette.mode === 'dark' 
              ? 'rgba(255, 255, 255, 0.1)' 
              : 'rgba(0, 0, 0, 0.1)',
          }}
        >
          <DeviceThermostatIcon 
            color="primary" 
            sx={{ 
              fontSize: 48, 
              opacity: 0.7 
            }} 
          />
          
          <Typography variant="h6" align="center">
            {t('devices.noDevices')}
          </Typography>
          
          <Typography variant="body2" color="text.secondary" align="center">
            {t('devices.addPrompt')}
          </Typography>
          
          <Button
            variant="contained"
            startIcon={<AddIcon />}
            onClick={handleAddDevice}
            size="large"
            sx={{ 
              px: 3,
              py: 1,
              borderRadius: 2,
              mt: 1
            }}
          >
            {t('devices.add')}
          </Button>
        </Paper>
      </Fade>
    );
  }
  
  return (
    <Fade in={animateIn} timeout={800}>
      <Box>
        <Box sx={{ 
          display: 'flex', 
          justifyContent: 'space-between', 
          alignItems: 'center', 
          mb: 2 
        }}>
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
            <DeviceThermostatIcon color="primary" />
            <Typography variant="h6" fontWeight="medium">
              {t('devices.title')}
            </Typography>
            <Chip 
              label={`${devices.length} ${devices.length === 1 ? 'device' : 'devices'}`} 
              size="small" 
              color="primary" 
              variant="outlined"
              sx={{ ml: 1, borderRadius: 1 }}
            />
          </Box>
          
          <Box>
            <Tooltip title={t('button.refresh')} arrow>
              <IconButton 
                onClick={handleRefresh} 
                size="small" 
                color="primary"
                sx={{ mr: 1 }}
              >
                <RefreshIcon />
              </IconButton>
            </Tooltip>
            
            <Tooltip title={t('devices.add')} arrow>
              <Button
                variant="outlined"
                size="small"
                onClick={handleAddDevice}
                startIcon={<AddIcon />}
                sx={{ borderRadius: 1 }}
              >
                {t('devices.add')}
              </Button>
            </Tooltip>
          </Box>
        </Box>
        
        <Box sx={{ 
          display: 'flex', 
          flexDirection: { xs: 'column', sm: 'row' }, 
          gap: 2, 
          alignItems: 'flex-start' 
        }}>
          <Autocomplete
            id="device-select"
            fullWidth
            value={selectedDevice || null}
            onChange={(_, newValue) => {
              if (newValue) {
                dispatch(setSelectedDevice(newValue.id));
                // Reset probe selection when changing devices
                dispatch(setSelectedProbe(null));
              }
            }}
            options={devices}
            getOptionLabel={(option) => option.nickname || option.deviceId}
            renderInput={(params) => (
              <TextField 
                {...params} 
                label={t('devices.name')} 
                variant="outlined"
                InputProps={{
                  ...params.InputProps,
                  startAdornment: (
                    <>
                      <InputAdornment position="start">
                        <DeviceThermostatIcon color="action" />
                      </InputAdornment>
                      {params.InputProps.startAdornment}
                    </>
                  ),
                }}
              />
            )}
            renderOption={(props, option) => (
              <MenuItem {...props} key={option.id}>
                <Box sx={{ display: 'flex', alignItems: 'center', width: '100%', gap: 1 }}>
                  <Avatar 
                    sx={{ 
                      width: 28, 
                      height: 28, 
                      bgcolor: 'primary.main',
                      fontSize: '0.8rem'
                    }}
                  >
                    {option.deviceType?.charAt(0) || 'D'}
                  </Avatar>
                  <Box sx={{ flexGrow: 1 }}>
                    <Typography variant="body1">
                      {option.nickname || option.deviceId}
                    </Typography>
                    <Typography variant="body2" color="text.secondary">
                      {option.deviceType || 'Unknown device'} • {option.probes?.length || 0} probes
                    </Typography>
                  </Box>
                  
                  {/* Status indicators */}
                  <Box sx={{ display: 'flex', gap: 0.5, alignItems: 'center' }}>
                    {option.batteryLevel !== undefined && (
                      <Tooltip title={`Battery: ${option.batteryLevel}%`} arrow>
                        <Box>
                          {getBatteryIcon(option.batteryLevel)}
                        </Box>
                      </Tooltip>
                    )}
                    
                    {option.signalStrength !== undefined && (
                      <Tooltip title={`Signal: ${option.signalStrength}%`} arrow>
                        <Box>
                          <SignalCellularAltIcon 
                            color={option.signalStrength > 50 ? "success" : "warning"} 
                            fontSize="small"
                          />
                        </Box>
                      </Tooltip>
                    )}
                  </Box>
                </Box>
              </MenuItem>
            )}
          />
          
          <Autocomplete
            id="probe-select"
            fullWidth
            disabled={!selectedDeviceId || probes.length === 0}
            value={selectedProbe || null}
            onChange={(_, newValue) => {
              dispatch(setSelectedProbe(newValue?.id || null));
            }}
            options={probes}
            getOptionLabel={(option) => option.name || `Probe ${option.probeId}`}
            renderInput={(params) => (
              <TextField 
                {...params} 
                label={t('devices.probes')} 
                variant="outlined"
                InputProps={{
                  ...params.InputProps,
                  startAdornment: (
                    <>
                      <InputAdornment position="start">
                        <SensorsIcon color="action" />
                      </InputAdornment>
                      {params.InputProps.startAdornment}
                    </>
                  ),
                }}
              />
            )}
            renderOption={(props, option) => (
              <MenuItem {...props} key={option.id}>
                <Box sx={{ display: 'flex', alignItems: 'center', width: '100%' }}>
                  <Typography sx={{ flexGrow: 1 }}>
                    {option.name || `Probe ${option.probeId}`}
                  </Typography>
                  
                  {option.status && (
                    <Chip 
                      label={option.status} 
                      size="small"
                      color={option.status === 'online' ? 'success' : 'default'}
                      variant="outlined"
                      sx={{ borderRadius: 1, ml: 1 }}
                    />
                  )}
                </Box>
              </MenuItem>
            )}
          />
        </Box>
      </Box>
    </Fade>
  );
};

export default DeviceSelector;