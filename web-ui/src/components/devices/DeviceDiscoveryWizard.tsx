import { useState } from 'react';
import {
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  Stepper,
  Step,
  StepLabel,
  Button,
  Typography,
  TextField,
  Box,
  CircularProgress,
  List,
  ListItem,
  ListItemText,
  ListItemIcon,
  Radio,
  Divider,
  Alert,
} from '@mui/material';
import DevicesIcon from '@mui/icons-material/Devices';
import CheckCircleIcon from '@mui/icons-material/CheckCircle';
import { useAppDispatch, useAppSelector } from '@/hooks/reduxHooks';
import { selectDeviceDiscoveryOpen, closeDeviceDiscovery } from '@/store/slices/deviceSlice';
import { api } from '@/store/api';
import useAlerts from '@/hooks/useAlerts';

interface DiscoveredDevice {
  id: string;
  name: string;
  type: string;
  status: string;
}

/**
 * Wizard for discovering and adding ThermoWorks devices
 */
const DeviceDiscoveryWizard = () => {
  const dispatch = useAppDispatch();
  const { showSuccess, showError } = useAlerts();
  const open = useAppSelector(selectDeviceDiscoveryOpen);
  
  const [activeStep, setActiveStep] = useState(0);
  const [scanning, setScanning] = useState(false);
  const [discoveredDevices, setDiscoveredDevices] = useState<DiscoveredDevice[]>([]);
  const [selectedDeviceId, setSelectedDeviceId] = useState<string | null>(null);
  const [deviceNickname, setDeviceNickname] = useState('');
  
  // API hooks
  const [registerDevice, { isLoading: isRegistering }] = api.useRegisterDeviceMutation();
  
  // Step definitions
  const steps = ['Discover Devices', 'Configure Device', 'Complete'];
  
  // Handle discovery step
  const handleScanDevices = async () => {
    setScanning(true);
    
    // Simulate device discovery (in a real app, this would be an API call)
    setTimeout(() => {
      // Mock discovered devices
      setDiscoveredDevices([
        { id: 'TW-ABC-123', name: 'Signals BBQ', type: 'Signals', status: 'available' },
        { id: 'TW-DEF-456', name: 'Smoke X4', type: 'Smoke', status: 'available' },
        { id: 'TW-GHI-789', name: 'DOT', type: 'DOT', status: 'available' },
      ]);
      setScanning(false);
    }, 2000);
  };
  
  const handleDeviceSelect = (deviceId: string) => {
    setSelectedDeviceId(deviceId);
    
    // Set default nickname based on device type
    const device = discoveredDevices.find(d => d.id === deviceId);
    if (device) {
      setDeviceNickname(device.name);
    }
  };
  
  // Handle device registration
  const handleRegisterDevice = async () => {
    if (!selectedDeviceId) return;
    
    try {
      await registerDevice({
        deviceId: selectedDeviceId,
        nickname: deviceNickname || undefined,
      }).unwrap();
      
      // Advance to completion step
      setActiveStep(2);
      showSuccess(`Device ${selectedDeviceId} successfully registered`);
    } catch (error) {
      showError(`Failed to register device: ${error instanceof Error ? error.message : 'Unknown error'}`);
    }
  };
  
  // Handle step navigation
  const handleNext = () => {
    if (activeStep === 0) {
      if (!selectedDeviceId) {
        showError('Please select a device to continue');
        return;
      }
    } else if (activeStep === 1) {
      handleRegisterDevice();
      return;
    }
    
    setActiveStep((prevStep) => prevStep + 1);
  };
  
  const handleBack = () => {
    setActiveStep((prevStep) => prevStep - 1);
  };
  
  const handleClose = () => {
    dispatch(closeDeviceDiscovery());
    
    // Reset state
    setActiveStep(0);
    setScanning(false);
    setDiscoveredDevices([]);
    setSelectedDeviceId(null);
    setDeviceNickname('');
  };
  
  // Render step content
  const getStepContent = (step: number) => {
    switch (step) {
      case 0:
        return (
          <Box>
            <Typography variant="body1" paragraph>
              Search for available ThermoWorks devices on your network.
            </Typography>
            
            {discoveredDevices.length === 0 ? (
              <Box sx={{ textAlign: 'center', py: 3 }}>
                {scanning ? (
                  <>
                    <CircularProgress size={40} sx={{ mb: 2 }} />
                    <Typography>Scanning for devices...</Typography>
                  </>
                ) : (
                  <>
                    <DevicesIcon sx={{ fontSize: 60, color: 'primary.main', mb: 2 }} />
                    <Typography>
                      No devices found. Click "Scan" to discover available devices.
                    </Typography>
                    <Button 
                      variant="contained" 
                      onClick={handleScanDevices} 
                      sx={{ mt: 2 }}
                    >
                      Scan
                    </Button>
                  </>
                )}
              </Box>
            ) : (
              <>
                <Typography variant="subtitle1" sx={{ mt: 2, mb: 1 }}>
                  Available Devices
                </Typography>
                <List>
                  {discoveredDevices.map((device) => (
                    <Box key={device.id}>
                      <ListItem
                        button
                        selected={selectedDeviceId === device.id}
                        onClick={() => handleDeviceSelect(device.id)}
                      >
                        <ListItemIcon>
                          <Radio
                            checked={selectedDeviceId === device.id}
                            onChange={() => handleDeviceSelect(device.id)}
                          />
                        </ListItemIcon>
                        <ListItemText
                          primary={device.name}
                          secondary={`ID: ${device.id} • Type: ${device.type}`}
                        />
                      </ListItem>
                      <Divider />
                    </Box>
                  ))}
                </List>
                
                <Box sx={{ mt: 2, textAlign: 'center' }}>
                  <Button 
                    variant="outlined" 
                    onClick={handleScanDevices} 
                    disabled={scanning}
                    startIcon={scanning ? <CircularProgress size={20} /> : undefined}
                  >
                    {scanning ? 'Scanning...' : 'Scan Again'}
                  </Button>
                </Box>
              </>
            )}
          </Box>
        );
        
      case 1:
        return (
          <Box>
            <Typography variant="body1" paragraph>
              Configure your ThermoWorks device before adding it to your account.
            </Typography>
            
            {selectedDeviceId && (
              <Box sx={{ mt: 3 }}>
                <Typography variant="subtitle1" gutterBottom>
                  Device Information
                </Typography>
                <Typography variant="body2">
                  ID: {selectedDeviceId}
                </Typography>
                <Typography variant="body2" sx={{ mb: 3 }}>
                  Type: {discoveredDevices.find(d => d.id === selectedDeviceId)?.type}
                </Typography>
                
                <TextField
                  label="Device Nickname"
                  value={deviceNickname}
                  onChange={(e) => setDeviceNickname(e.target.value)}
                  fullWidth
                  margin="normal"
                  helperText="Give your device a name to easily identify it"
                />
                
                <Alert severity="info" sx={{ mt: 3 }}>
                  After registering, your device will appear in your dashboard and you can begin monitoring temperatures.
                </Alert>
              </Box>
            )}
          </Box>
        );
        
      case 2:
        return (
          <Box sx={{ textAlign: 'center', py: 3 }}>
            <CheckCircleIcon sx={{ fontSize: 60, color: 'success.main', mb: 2 }} />
            <Typography variant="h6" gutterBottom>
              Device Successfully Added
            </Typography>
            <Typography variant="body1" paragraph>
              Your ThermoWorks device has been registered and is ready to use.
            </Typography>
            <Typography variant="body2" color="text.secondary">
              You can now select it in the dashboard to monitor temperatures.
            </Typography>
          </Box>
        );
        
      default:
        return 'Unknown step';
    }
  };
  
  return (
    <Dialog open={open} onClose={handleClose} maxWidth="sm" fullWidth>
      <DialogTitle>Add ThermoWorks Device</DialogTitle>
      
      <DialogContent>
        <Stepper activeStep={activeStep} alternativeLabel sx={{ mb: 4 }}>
          {steps.map((label) => (
            <Step key={label}>
              <StepLabel>{label}</StepLabel>
            </Step>
          ))}
        </Stepper>
        
        {getStepContent(activeStep)}
      </DialogContent>
      
      <DialogActions>
        <Button onClick={handleClose}>
          {activeStep === steps.length - 1 ? 'Finish' : 'Cancel'}
        </Button>
        
        {activeStep > 0 && activeStep < steps.length - 1 && (
          <Button onClick={handleBack} disabled={scanning}>
            Back
          </Button>
        )}
        
        {activeStep < steps.length - 1 && (
          <Button 
            variant="contained" 
            onClick={handleNext}
            disabled={
              (activeStep === 0 && (!selectedDeviceId || scanning)) ||
              (activeStep === 1 && isRegistering)
            }
            startIcon={isRegistering ? <CircularProgress size={20} /> : undefined}
          >
            {activeStep === steps.length - 2 ? 'Register' : 'Next'}
          </Button>
        )}
      </DialogActions>
    </Dialog>
  );
};

export default DeviceDiscoveryWizard;