import { useState } from 'react';
import {
  Box,
  Grid,
  Typography,
  Button,
  FormControlLabel,
  Switch,
  CircularProgress,
  Divider,
  Paper,
} from '@mui/material';
import AddIcon from '@mui/icons-material/Add';
import RefreshIcon from '@mui/icons-material/Refresh';
import PageContainer from '@/components/common/PageContainer';
import DeviceCard from '@/components/devices/DeviceCard';
import DeviceDiscoveryWizard from '@/components/devices/DeviceDiscoveryWizard';
import { useAppDispatch } from '@/hooks/reduxHooks';
import { openDeviceDiscovery } from '@/store/slices/deviceSlice';
import { api } from '@/store/api';

/**
 * Device management page for adding, editing, and removing devices
 */
const DeviceManagementPage = () => {
  const dispatch = useAppDispatch();
  
  const [includeInactive, setIncludeInactive] = useState(false);
  const [refreshKey, setRefreshKey] = useState(0);
  
  // Fetch devices
  const { data: devicesResponse, isLoading, error, refetch } = api.useGetDevicesQuery({
    includeInactive,
  });
  
  const devices = devicesResponse?.data.devices || [];
  
  // Open device discovery wizard
  const handleAddDevice = () => {
    dispatch(openDeviceDiscovery());
  };
  
  // Force refresh
  const handleRefresh = () => {
    refetch();
    setRefreshKey(prev => prev + 1);
  };
  
  // Toggle showing inactive devices
  const handleToggleInactive = (event: React.ChangeEvent<HTMLInputElement>) => {
    setIncludeInactive(event.target.checked);
  };
  
  return (
    <PageContainer 
      title="Device Management" 
      description="Add, configure, and manage your ThermoWorks devices"
      paper={false}
    >
      <Box sx={{ 
        display: 'flex', 
        flexDirection: { xs: 'column', sm: 'row' },
        justifyContent: 'space-between', 
        alignItems: { xs: 'flex-start', sm: 'center' },
        mb: 3,
        gap: 2,
      }}>
        <Button 
          variant="contained" 
          startIcon={<AddIcon />}
          onClick={handleAddDevice}
        >
          Add Device
        </Button>
        
        <Box sx={{ 
          display: 'flex', 
          alignItems: 'center',
          gap: 2,
          flexWrap: 'wrap',
          ml: { xs: 0, sm: 'auto' }
        }}>
          <FormControlLabel
            control={
              <Switch
                checked={includeInactive}
                onChange={handleToggleInactive}
                color="primary"
              />
            }
            label="Show inactive devices"
          />
          
          <Button 
            startIcon={<RefreshIcon />} 
            onClick={handleRefresh}
            variant="outlined"
            size="small"
          >
            Refresh
          </Button>
        </Box>
      </Box>
      
      <Divider sx={{ mb: 3 }} />
      
      {isLoading ? (
        <Box sx={{ display: 'flex', justifyContent: 'center', py: 4 }}>
          <CircularProgress />
        </Box>
      ) : error ? (
        <Paper sx={{ p: 3, bgcolor: 'error.light', color: 'error.contrastText' }}>
          <Typography>Error loading devices. Please try again.</Typography>
        </Paper>
      ) : devices.length === 0 ? (
        <Paper 
          sx={{ 
            p: 6, 
            textAlign: 'center',
            display: 'flex',
            flexDirection: 'column',
            alignItems: 'center',
            gap: 2,
          }}
        >
          <Typography variant="h6" gutterBottom>
            No Devices Found
          </Typography>
          <Typography variant="body1" color="text.secondary" paragraph>
            {includeInactive
              ? "You don't have any devices registered yet."
              : "You don't have any active devices. Try enabling 'Show inactive devices' to see all your devices."}
          </Typography>
          <Button 
            variant="contained" 
            startIcon={<AddIcon />}
            onClick={handleAddDevice}
          >
            Add Your First Device
          </Button>
        </Paper>
      ) : (
        <Grid container spacing={3}>
          {devices.map((device) => (
            <Grid item xs={12} sm={6} md={4} key={device.id}>
              <DeviceCard 
                key={`${device.id}-${refreshKey}`}
                device={device} 
                onRefresh={handleRefresh}
              />
            </Grid>
          ))}
        </Grid>
      )}
      
      {/* Device Discovery Wizard */}
      <DeviceDiscoveryWizard />
    </PageContainer>
  );
};

export default DeviceManagementPage;