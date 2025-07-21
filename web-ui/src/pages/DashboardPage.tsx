import { useState, useEffect } from 'react';
import { useTranslation } from 'react-i18next';
import { 
  Box, 
  Grid, 
  Typography, 
  Button, 
  Paper, 
  Card, 
  CardContent, 
  Divider,
  Zoom,
  Fade,
  Chip,
  Badge,
  useMediaQuery,
  useTheme
} from '@mui/material';
import AddIcon from '@mui/icons-material/Add';
import RefreshIcon from '@mui/icons-material/Refresh';
import SpeedIcon from '@mui/icons-material/Speed';
import AccessTimeIcon from '@mui/icons-material/AccessTime';
import PageContainer from '@/components/common/PageContainer';
import DeviceSelector from '@/components/dashboard/DeviceSelector';
import TemperatureCard from '@/components/dashboard/TemperatureCard';
import TemperatureChart from '@/components/charts/TemperatureChart';
import ChartControls from '@/components/charts/ChartControls';
import DeviceDiscoveryWizard from '@/components/devices/DeviceDiscoveryWizard';
import { useAppDispatch, useAppSelector } from '@/hooks/reduxHooks';
import { selectSelectedDevice, selectSelectedProbe, openDeviceDiscovery } from '@/store/slices/deviceSlice';
import { api } from '@/store/api';
import useResponsive from '@/hooks/useResponsive';

/**
 * Enhanced main dashboard page with improved layout and animations
 */
const DashboardPage = () => {
  const { t } = useTranslation();
  const dispatch = useAppDispatch();
  const isMobile = useResponsive();
  const theme = useTheme();
  const isTablet = useMediaQuery(theme.breakpoints.down('md'));
  const isSmallScreen = useMediaQuery(theme.breakpoints.down('sm'));
  
  const selectedDeviceId = useAppSelector(selectSelectedDevice);
  const selectedProbeId = useAppSelector(selectSelectedProbe);
  
  const [refreshKey, setRefreshKey] = useState(0);
  const [lastRefreshTime, setLastRefreshTime] = useState<Date>(new Date());
  const [loaded, setLoaded] = useState(false);
  
  // Animation on mount
  useEffect(() => {
    setLoaded(true);
  }, []);
  
  // Fetch selected device details
  const { data: deviceData, refetch: refetchDevice, isLoading } = api.useGetDeviceByIdQuery(
    selectedDeviceId || '',
    { skip: !selectedDeviceId }
  );
  
  // Get probes for the selected device
  const device = deviceData?.data;
  const probes = device?.probes || [];
  
  // Find selected probe
  const selectedProbe = selectedProbeId 
    ? probes.find(probe => probe.id === selectedProbeId) 
    : undefined;
  
  // Force refresh
  const handleRefresh = () => {
    refetchDevice();
    setRefreshKey(prev => prev + 1);
    setLastRefreshTime(new Date());
  };
  
  // Open device discovery wizard
  const handleAddDevice = () => {
    dispatch(openDeviceDiscovery());
  };
  
  // Format last refresh time
  const getRefreshTimeDisplay = () => {
    const now = new Date();
    const diff = Math.floor((now.getTime() - lastRefreshTime.getTime()) / 1000);
    
    if (diff < 60) {
      return `${diff} ${diff === 1 ? 'second' : 'seconds'} ago`;
    } else if (diff < 3600) {
      const minutes = Math.floor(diff / 60);
      return `${minutes} ${minutes === 1 ? 'minute' : 'minutes'} ago`;
    } else {
      return lastRefreshTime.toLocaleTimeString();
    }
  };
  
  // If no device is selected, show prompt
  if (!selectedDeviceId) {
    return (
      <PageContainer 
        title={t('dashboard.title')}
        description={t('dashboard.description')}
      >
        <Fade in={loaded} timeout={800}>
          <Box 
            sx={{ 
              textAlign: 'center', 
              py: 8,
              px: 2,
              maxWidth: 600,
              mx: 'auto'
            }}
          >
            <Card 
              elevation={3}
              sx={{ 
                p: 4, 
                borderRadius: 4,
                backgroundColor: theme.palette.mode === 'dark' 
                  ? 'rgba(30, 30, 30, 0.7)'
                  : 'rgba(255, 255, 255, 0.7)',
                backdropFilter: 'blur(10px)',
                boxShadow: theme.palette.mode === 'dark'
                  ? '0 8px 32px rgba(0, 0, 0, 0.3)'
                  : '0 8px 32px rgba(100, 100, 100, 0.2)',
              }}
            >
              <SpeedIcon 
                color="primary" 
                sx={{ 
                  fontSize: 80, 
                  mb: 2,
                  opacity: 0.7
                }} 
              />
              
              <Typography 
                variant="h4" 
                gutterBottom
                fontWeight="medium"
                color="primary"
              >
                {t('dashboard.noDeviceSelected')}
              </Typography>
              
              <Typography 
                variant="body1" 
                color="text.secondary" 
                paragraph
                sx={{ mb: 4 }}
              >
                {t('dashboard.selectDevicePrompt')}
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
                  boxShadow: '0 4px 14px rgba(244, 67, 54, 0.4)',
                  '&:hover': {
                    boxShadow: '0 6px 20px rgba(244, 67, 54, 0.6)',
                    transform: 'translateY(-2px)'
                  },
                  transition: 'all 0.2s ease',
                }}
              >
                {t('devices.add')}
              </Button>
            </Card>
            
            <DeviceDiscoveryWizard />
          </Box>
        </Fade>
      </PageContainer>
    );
  }
  
  return (
    <PageContainer 
      title={t('dashboard.title')}
      description={t('dashboard.description')}
      paper={false}
    >
      <Fade in={loaded} timeout={800}>
        <Grid container spacing={3}>
          {/* Header with Device Selector */}
          <Grid item xs={12}>
            <Card 
              elevation={2}
              sx={{ 
                borderRadius: 3,
                overflow: 'hidden',
                mb: 1,
                background: theme.palette.mode === 'dark' 
                  ? 'linear-gradient(145deg, #1e1e1e 30%, #2d2d2d 90%)'
                  : 'linear-gradient(145deg, #ffffff 30%, #f5f5f5 90%)',
              }}
            >
              <CardContent sx={{ p: isSmallScreen ? 2 : 3 }}>
                <DeviceSelector />
                
                <Box 
                  sx={{ 
                    display: 'flex', 
                    justifyContent: 'space-between', 
                    alignItems: 'center',
                    mt: 2,
                    flexWrap: 'wrap',
                    gap: 1
                  }}
                >
                  <Box sx={{ display: 'flex', alignItems: 'center' }}>
                    <AccessTimeIcon 
                      color="action" 
                      fontSize="small" 
                      sx={{ mr: 1, opacity: 0.7 }} 
                    />
                    <Typography variant="body2" color="text.secondary">
                      {t('dashboard.refresh')}: {getRefreshTimeDisplay()}
                    </Typography>
                  </Box>
                  
                  <Button 
                    variant="outlined"
                    startIcon={<RefreshIcon />} 
                    onClick={handleRefresh}
                    size="small"
                    disabled={isLoading}
                    sx={{ 
                      borderRadius: 2,
                      '&:hover': {
                        transform: 'rotate(180deg)',
                        transition: 'transform 0.5s'
                      }
                    }}
                  >
                    {t('button.refresh')}
                  </Button>
                </Box>
              </CardContent>
            </Card>
          </Grid>
          
          {/* Temperature Cards */}
          <Grid item xs={12}>
            <Card 
              elevation={2}
              sx={{ 
                borderRadius: 3,
                mb: 1,
                background: theme.palette.mode === 'dark' 
                  ? 'linear-gradient(145deg, #1e1e1e 30%, #2d2d2d 90%)'
                  : 'linear-gradient(145deg, #ffffff 30%, #f5f5f5 90%)',
              }}
            >
              <CardContent sx={{ p: isSmallScreen ? 2 : 3 }}>
                <Box sx={{ 
                  display: 'flex', 
                  justifyContent: 'space-between', 
                  alignItems: 'center',
                  mb: 3
                }}>
                  <Typography 
                    variant="h6" 
                    fontWeight="medium"
                    sx={{ 
                      display: 'flex', 
                      alignItems: 'center', 
                      gap: 1
                    }}
                  >
                    <SpeedIcon color="primary" />
                    {t('dashboard.currentTemperatures')}
                  </Typography>
                  
                  <Chip 
                    label={`${probes.length} ${probes.length === 1 ? 'probe' : 'probes'}`} 
                    size="small" 
                    color="primary" 
                    variant="outlined"
                    sx={{ borderRadius: 1 }}
                  />
                </Box>
                
                <Grid container spacing={isSmallScreen ? 2 : 3}>
                  {selectedProbe ? (
                    // Show only selected probe
                    <Zoom in={true} style={{ transitionDelay: '100ms' }}>
                      <Grid item xs={12} sm={6} md={4}>
                        <TemperatureCard 
                          key={`${selectedDeviceId}-${selectedProbeId}-${refreshKey}`}
                          deviceId={selectedDeviceId}
                          probeId={selectedProbeId}
                          probe={selectedProbe}
                        />
                      </Grid>
                    </Zoom>
                  ) : (
                    // Show all probes
                    probes.length > 0 ? (
                      probes.map((probe, index) => (
                        <Zoom 
                          in={true} 
                          style={{ transitionDelay: `${index * 100}ms` }}
                          key={probe.id}
                        >
                          <Grid item xs={12} sm={6} md={4}>
                            <TemperatureCard 
                              key={`${selectedDeviceId}-${probe.id}-${refreshKey}`}
                              deviceId={selectedDeviceId}
                              probeId={probe.id}
                              probe={probe}
                            />
                          </Grid>
                        </Zoom>
                      ))
                    ) : (
                      <Grid item xs={12}>
                        <Paper 
                          elevation={0}
                          sx={{ 
                            p: 3, 
                            textAlign: 'center',
                            borderRadius: 2,
                            backgroundColor: theme.palette.mode === 'dark' 
                              ? 'rgba(30, 30, 30, 0.5)' 
                              : 'rgba(245, 245, 245, 0.5)'
                          }}
                        >
                          <Typography color="text.secondary">
                            {t('dashboard.noProbes')}
                          </Typography>
                        </Paper>
                      </Grid>
                    )
                  )}
                </Grid>
              </CardContent>
            </Card>
          </Grid>
          
          {/* Temperature Chart */}
          <Grid item xs={12}>
            <Card 
              elevation={2}
              sx={{ 
                borderRadius: 3,
                background: theme.palette.mode === 'dark' 
                  ? 'linear-gradient(145deg, #1e1e1e 30%, #2d2d2d 90%)'
                  : 'linear-gradient(145deg, #ffffff 30%, #f5f5f5 90%)',
              }}
            >
              <CardContent sx={{ p: isSmallScreen ? 2 : 3 }}>
                <Box sx={{ 
                  display: 'flex', 
                  justifyContent: 'space-between', 
                  alignItems: 'center',
                  mb: 3 
                }}>
                  <Typography 
                    variant="h6" 
                    fontWeight="medium"
                    sx={{ 
                      display: 'flex', 
                      alignItems: 'center', 
                      gap: 1
                    }}
                  >
                    {t('dashboard.temperatureHistory')}
                  </Typography>
                </Box>
                
                <ChartControls 
                  deviceId={selectedDeviceId}
                  probeId={selectedProbeId}
                  onRefresh={handleRefresh}
                />
                
                <Box sx={{ mt: 3 }}>
                  <TemperatureChart 
                    key={`chart-${selectedDeviceId}-${selectedProbeId}-${refreshKey}`}
                    deviceId={selectedDeviceId}
                    probeId={selectedProbeId}
                    probes={selectedProbe ? [selectedProbe] : probes}
                    height={isSmallScreen ? 300 : isTablet ? 350 : 400}
                  />
                </Box>
              </CardContent>
            </Card>
          </Grid>
        </Grid>
      </Fade>
      
      {/* Device Discovery Wizard */}
      <DeviceDiscoveryWizard />
    </PageContainer>
  );
};

export default DashboardPage;