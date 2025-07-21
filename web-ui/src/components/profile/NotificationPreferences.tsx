import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { 
  Box, 
  Typography, 
  Switch, 
  FormGroup,
  FormControlLabel,
  Divider,
  Button,
  CircularProgress,
  Paper,
  Card,
  CardContent,
  CardHeader,
  List,
  ListItem,
  ListItemText,
  ListItemIcon,
  ListItemSecondaryAction,
  useTheme,
  IconButton,
  Tooltip
} from '@mui/material';
import ThermostatIcon from '@mui/icons-material/Thermostat';
import NotificationsIcon from '@mui/icons-material/Notifications';
import EmailIcon from '@mui/icons-material/Email';
import SmartphoneIcon from '@mui/icons-material/Smartphone';
import HelpOutlineIcon from '@mui/icons-material/HelpOutline';
import BatteryAlertIcon from '@mui/icons-material/BatteryAlert';
import ErrorOutlineIcon from '@mui/icons-material/ErrorOutline';
import ReportProblemIcon from '@mui/icons-material/ReportProblem';
import SaveIcon from '@mui/icons-material/Save';
import useAlerts from '@/hooks/useAlerts';

/**
 * Component for managing user notification preferences
 */
const NotificationPreferences = () => {
  const { t } = useTranslation();
  const theme = useTheme();
  const { showSuccess } = useAlerts();
  
  const [loading, setLoading] = useState(false);
  
  // Notification channels
  const [channels, setChannels] = useState({
    inApp: true,
    email: false,
    push: true,
  });
  
  // Temperature alert preferences
  const [tempAlerts, setTempAlerts] = useState({
    highTemp: true,
    lowTemp: true,
    targetReached: true,
    deviceDisconnected: true,
    batteryLow: true,
  });
  
  const handleChannelChange = (event: React.ChangeEvent<HTMLInputElement>) => {
    setChannels({
      ...channels,
      [event.target.name]: event.target.checked,
    });
  };
  
  const handleTempAlertChange = (event: React.ChangeEvent<HTMLInputElement>) => {
    setTempAlerts({
      ...tempAlerts,
      [event.target.name]: event.target.checked,
    });
  };
  
  const handleSavePreferences = async () => {
    setLoading(true);
    
    try {
      // Here we would make an API call to save the preferences
      // For now, let's simulate it with a timeout
      await new Promise(resolve => setTimeout(resolve, 1000));
      
      showSuccess(t('profile.preferencesUpdated'));
    } finally {
      setLoading(false);
    }
  };
  
  return (
    <Box>
      <Typography variant="h6" gutterBottom sx={{ mb: 3 }}>
        {t('profile.notificationSettings')}
      </Typography>
      
      <Box sx={{ mb: 4 }}>
        <Typography variant="subtitle1" gutterBottom fontWeight="medium">
          {t('profile.notificationChannels')}
        </Typography>
        
        <Card 
          variant="outlined" 
          sx={{ 
            borderRadius: 2,
            mb: 3
          }}
        >
          <List>
            <ListItem>
              <ListItemIcon>
                <NotificationsIcon color="primary" />
              </ListItemIcon>
              <ListItemText 
                primary={t('profile.inAppNotifications')} 
                secondary={t('profile.inAppDescription')}
              />
              <ListItemSecondaryAction>
                <Switch
                  edge="end"
                  name="inApp"
                  checked={channels.inApp}
                  onChange={handleChannelChange}
                  inputProps={{ 'aria-labelledby': 'switch-in-app' }}
                />
              </ListItemSecondaryAction>
            </ListItem>
            
            <Divider variant="inset" component="li" />
            
            <ListItem>
              <ListItemIcon>
                <EmailIcon color="primary" />
              </ListItemIcon>
              <ListItemText 
                primary={t('profile.emailNotifications')} 
                secondary={t('profile.emailDescription')}
              />
              <ListItemSecondaryAction>
                <Switch
                  edge="end"
                  name="email"
                  checked={channels.email}
                  onChange={handleChannelChange}
                  inputProps={{ 'aria-labelledby': 'switch-email' }}
                />
              </ListItemSecondaryAction>
            </ListItem>
            
            <Divider variant="inset" component="li" />
            
            <ListItem>
              <ListItemIcon>
                <SmartphoneIcon color="primary" />
              </ListItemIcon>
              <ListItemText 
                primary={t('profile.pushNotifications')} 
                secondary={t('profile.pushDescription')}
              />
              <ListItemSecondaryAction>
                <Switch
                  edge="end"
                  name="push"
                  checked={channels.push}
                  onChange={handleChannelChange}
                  inputProps={{ 'aria-labelledby': 'switch-push' }}
                />
              </ListItemSecondaryAction>
            </ListItem>
          </List>
        </Card>
      </Box>
      
      <Box sx={{ mb: 4 }}>
        <Box sx={{ display: 'flex', alignItems: 'center', mb: 2 }}>
          <Typography variant="subtitle1" fontWeight="medium">
            {t('profile.temperatureAlerts')}
          </Typography>
          <Tooltip title={t('profile.alertsTooltip')} arrow>
            <IconButton size="small" sx={{ ml: 1 }}>
              <HelpOutlineIcon fontSize="small" />
            </IconButton>
          </Tooltip>
        </Box>
        
        <Card 
          variant="outlined" 
          sx={{ 
            borderRadius: 2
          }}
        >
          <List>
            <ListItem>
              <ListItemIcon>
                <ThermostatIcon color="error" />
              </ListItemIcon>
              <ListItemText 
                primary={t('profile.highTempAlerts')} 
                secondary={t('profile.highTempDescription')}
              />
              <ListItemSecondaryAction>
                <Switch
                  edge="end"
                  name="highTemp"
                  checked={tempAlerts.highTemp}
                  onChange={handleTempAlertChange}
                  inputProps={{ 'aria-labelledby': 'switch-high-temp' }}
                  color="error"
                />
              </ListItemSecondaryAction>
            </ListItem>
            
            <Divider variant="inset" component="li" />
            
            <ListItem>
              <ListItemIcon>
                <ThermostatIcon color="info" />
              </ListItemIcon>
              <ListItemText 
                primary={t('profile.lowTempAlerts')} 
                secondary={t('profile.lowTempDescription')}
              />
              <ListItemSecondaryAction>
                <Switch
                  edge="end"
                  name="lowTemp"
                  checked={tempAlerts.lowTemp}
                  onChange={handleTempAlertChange}
                  inputProps={{ 'aria-labelledby': 'switch-low-temp' }}
                  color="info"
                />
              </ListItemSecondaryAction>
            </ListItem>
            
            <Divider variant="inset" component="li" />
            
            <ListItem>
              <ListItemIcon>
                <ThermostatIcon color="success" />
              </ListItemIcon>
              <ListItemText 
                primary={t('profile.targetTempAlerts')} 
                secondary={t('profile.targetTempDescription')}
              />
              <ListItemSecondaryAction>
                <Switch
                  edge="end"
                  name="targetReached"
                  checked={tempAlerts.targetReached}
                  onChange={handleTempAlertChange}
                  inputProps={{ 'aria-labelledby': 'switch-target-temp' }}
                  color="success"
                />
              </ListItemSecondaryAction>
            </ListItem>
            
            <Divider variant="inset" component="li" />
            
            <ListItem>
              <ListItemIcon>
                <ErrorOutlineIcon color="warning" />
              </ListItemIcon>
              <ListItemText 
                primary={t('profile.deviceDisconnectionAlerts')} 
                secondary={t('profile.deviceDisconnectionDescription')}
              />
              <ListItemSecondaryAction>
                <Switch
                  edge="end"
                  name="deviceDisconnected"
                  checked={tempAlerts.deviceDisconnected}
                  onChange={handleTempAlertChange}
                  inputProps={{ 'aria-labelledby': 'switch-device-disconnected' }}
                  color="warning"
                />
              </ListItemSecondaryAction>
            </ListItem>
            
            <Divider variant="inset" component="li" />
            
            <ListItem>
              <ListItemIcon>
                <BatteryAlertIcon color="warning" />
              </ListItemIcon>
              <ListItemText 
                primary={t('profile.batteryAlerts')} 
                secondary={t('profile.batteryDescription')}
              />
              <ListItemSecondaryAction>
                <Switch
                  edge="end"
                  name="batteryLow"
                  checked={tempAlerts.batteryLow}
                  onChange={handleTempAlertChange}
                  inputProps={{ 'aria-labelledby': 'switch-battery-low' }}
                  color="warning"
                />
              </ListItemSecondaryAction>
            </ListItem>
          </List>
        </Card>
      </Box>
      
      <Box sx={{ display: 'flex', justifyContent: 'flex-end', mt: 3 }}>
        <Button
          variant="contained"
          color="primary"
          startIcon={loading ? <CircularProgress size={20} /> : <SaveIcon />}
          onClick={handleSavePreferences}
          disabled={loading}
        >
          {loading ? t('button.saving') : t('button.savePreferences')}
        </Button>
      </Box>
    </Box>
  );
};

export default NotificationPreferences;