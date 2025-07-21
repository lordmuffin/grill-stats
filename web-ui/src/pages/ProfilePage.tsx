import { useState, useEffect } from 'react';
import { useTranslation } from 'react-i18next';
import { 
  Box, 
  Paper, 
  Typography, 
  Divider, 
  Avatar, 
  Button, 
  TextField, 
  Grid, 
  IconButton, 
  Tooltip, 
  CircularProgress,
  Fade,
  Alert,
  Stack,
  Card,
  CardContent,
  CardHeader,
  useTheme,
  Tab,
  Tabs,
  useMediaQuery
} from '@mui/material';
import EditIcon from '@mui/icons-material/Edit';
import SaveIcon from '@mui/icons-material/Save';
import CancelIcon from '@mui/icons-material/Cancel';
import SecurityIcon from '@mui/icons-material/Security';
import AccountCircleIcon from '@mui/icons-material/AccountCircle';
import VpnKeyIcon from '@mui/icons-material/VpnKey';
import NotificationsIcon from '@mui/icons-material/Notifications';
import { format } from 'date-fns';
import { useAppSelector, useAppDispatch } from '@/hooks/reduxHooks';
import { selectUser, selectAuthLoading } from '@/store/slices/authSlice';
import useAlerts from '@/hooks/useAlerts';
import DashboardLayout from '@/components/layout/DashboardLayout';
import PasswordChangeForm from '@/components/auth/PasswordChangeForm';
import NotificationPreferences from '@/components/profile/NotificationPreferences';
import { TabPanel, a11yProps } from '@/components/common/TabPanel';

/**
 * User profile page allowing users to view and edit their personal information,
 * change passwords, and manage notification preferences
 */
const ProfilePage = () => {
  const { t } = useTranslation();
  const theme = useTheme();
  const isMobile = useMediaQuery(theme.breakpoints.down('sm'));
  const dispatch = useAppDispatch();
  const user = useAppSelector(selectUser);
  const loading = useAppSelector(selectAuthLoading);
  const { showSuccess, showError } = useAlerts();
  
  const [editMode, setEditMode] = useState(false);
  const [tabValue, setTabValue] = useState(0);
  const [formValues, setFormValues] = useState({
    firstName: user?.firstName || '',
    lastName: user?.lastName || '',
    email: user?.email || '',
  });
  const [saving, setSaving] = useState(false);
  
  // Update form values when user data changes
  useEffect(() => {
    if (user) {
      setFormValues({
        firstName: user.firstName || '',
        lastName: user.lastName || '',
        email: user.email || '',
      });
    }
  }, [user]);
  
  const handleTabChange = (_: React.SyntheticEvent, newValue: number) => {
    setTabValue(newValue);
  };
  
  const handleInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const { name, value } = e.target;
    setFormValues({
      ...formValues,
      [name]: value,
    });
  };
  
  const handleEditToggle = () => {
    if (editMode) {
      // Cancel edit, reset form
      setFormValues({
        firstName: user?.firstName || '',
        lastName: user?.lastName || '',
        email: user?.email || '',
      });
    }
    setEditMode(!editMode);
  };
  
  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setSaving(true);
    
    try {
      // Here we would dispatch an API call to update user data
      // For now, we'll simulate it with a timeout
      await new Promise(resolve => setTimeout(resolve, 1000));
      
      showSuccess(t('profile.updateSuccess'));
      setEditMode(false);
    } catch (error) {
      showError(t('profile.updateError'));
    } finally {
      setSaving(false);
    }
  };
  
  // Generate user initials for avatar
  const getInitials = () => {
    const firstInitial = formValues.firstName ? formValues.firstName[0] : '';
    const lastInitial = formValues.lastName ? formValues.lastName[0] : '';
    
    if (firstInitial && lastInitial) {
      return `${firstInitial}${lastInitial}`;
    } else if (formValues.email) {
      return formValues.email[0].toUpperCase();
    }
    
    return '?';
  };
  
  if (loading) {
    return (
      <DashboardLayout>
        <Box sx={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: '50vh' }}>
          <CircularProgress />
        </Box>
      </DashboardLayout>
    );
  }
  
  if (!user) {
    return (
      <DashboardLayout>
        <Alert severity="error" sx={{ mt: 2 }}>
          {t('error.userDataNotFound')}
        </Alert>
      </DashboardLayout>
    );
  }
  
  return (
    <DashboardLayout>
      <Fade in={true} timeout={800}>
        <Box sx={{ p: { xs: 2, md: 3 } }}>
          <Typography variant="h4" component="h1" gutterBottom fontWeight="medium">
            {t('profile.title')}
          </Typography>
          
          <Divider sx={{ mb: 4 }} />
          
          <Grid container spacing={4}>
            {/* Profile Summary Card */}
            <Grid item xs={12} md={4}>
              <Card 
                elevation={2}
                sx={{ 
                  borderRadius: 2,
                  height: '100%',
                  transition: 'transform 0.2s, box-shadow 0.2s',
                  '&:hover': {
                    boxShadow: 6,
                    transform: 'translateY(-4px)'
                  }
                }}
              >
                <CardContent sx={{ display: 'flex', flexDirection: 'column', alignItems: 'center', p: 3 }}>
                  <Avatar 
                    sx={{ 
                      width: 100, 
                      height: 100, 
                      mb: 2,
                      bgcolor: theme.palette.primary.main,
                      fontSize: '2rem',
                      fontWeight: 'bold',
                      boxShadow: '0 4px 8px rgba(0,0,0,0.1)'
                    }}
                  >
                    {getInitials()}
                  </Avatar>
                  
                  <Typography variant="h5" component="div" gutterBottom>
                    {formValues.firstName || formValues.lastName
                      ? `${formValues.firstName} ${formValues.lastName}`
                      : formValues.email}
                  </Typography>
                  
                  <Typography color="text.secondary" sx={{ mb: 2 }}>
                    {formValues.email}
                  </Typography>
                  
                  <Divider sx={{ width: '100%', my: 2 }} />
                  
                  <Stack spacing={1} sx={{ width: '100%' }}>
                    <Box sx={{ display: 'flex', justifyContent: 'space-between' }}>
                      <Typography variant="body2" color="text.secondary">
                        {t('profile.memberSince')}
                      </Typography>
                      <Typography variant="body2" fontWeight="medium">
                        {user.createdAt ? format(new Date(user.createdAt), 'MMMM dd, yyyy') : '—'}
                      </Typography>
                    </Box>
                    
                    <Box sx={{ display: 'flex', justifyContent: 'space-between' }}>
                      <Typography variant="body2" color="text.secondary">
                        {t('profile.lastLogin')}
                      </Typography>
                      <Typography variant="body2" fontWeight="medium">
                        {user.lastLogin ? format(new Date(user.lastLogin), 'MMMM dd, yyyy') : '—'}
                      </Typography>
                    </Box>
                  </Stack>
                </CardContent>
              </Card>
            </Grid>
            
            {/* Tabs Section */}
            <Grid item xs={12} md={8}>
              <Card 
                elevation={2}
                sx={{ 
                  borderRadius: 2,
                  height: '100%',
                  overflow: 'hidden'
                }}
              >
                <Box sx={{ borderBottom: 1, borderColor: 'divider' }}>
                  <Tabs 
                    value={tabValue} 
                    onChange={handleTabChange}
                    aria-label="profile tabs"
                    variant={isMobile ? 'fullWidth' : 'standard'}
                    sx={{ 
                      '& .MuiTab-root': {
                        minHeight: 64,
                        py: 1.5,
                      }
                    }}
                  >
                    <Tab 
                      icon={<AccountCircleIcon />} 
                      label={t('profile.personalInfo')} 
                      {...a11yProps(0)} 
                      iconPosition="start"
                    />
                    <Tab 
                      icon={<VpnKeyIcon />} 
                      label={t('profile.password')} 
                      {...a11yProps(1)} 
                      iconPosition="start"
                    />
                    <Tab 
                      icon={<NotificationsIcon />} 
                      label={t('profile.notifications')} 
                      {...a11yProps(2)} 
                      iconPosition="start"
                    />
                  </Tabs>
                </Box>
                
                <TabPanel value={tabValue} index={0}>
                  <form onSubmit={handleSubmit}>
                    <Grid container spacing={3}>
                      <Grid item xs={12} sm={6}>
                        <TextField
                          fullWidth
                          label={t('profile.firstName')}
                          name="firstName"
                          value={formValues.firstName}
                          onChange={handleInputChange}
                          disabled={!editMode}
                          variant={editMode ? "outlined" : "filled"}
                          InputProps={{ readOnly: !editMode }}
                        />
                      </Grid>
                      
                      <Grid item xs={12} sm={6}>
                        <TextField
                          fullWidth
                          label={t('profile.lastName')}
                          name="lastName"
                          value={formValues.lastName}
                          onChange={handleInputChange}
                          disabled={!editMode}
                          variant={editMode ? "outlined" : "filled"}
                          InputProps={{ readOnly: !editMode }}
                        />
                      </Grid>
                      
                      <Grid item xs={12}>
                        <TextField
                          fullWidth
                          label={t('profile.email')}
                          name="email"
                          type="email"
                          value={formValues.email}
                          onChange={handleInputChange}
                          disabled={!editMode}
                          variant={editMode ? "outlined" : "filled"}
                          InputProps={{ readOnly: !editMode }}
                        />
                      </Grid>
                      
                      <Grid item xs={12}>
                        <Box sx={{ display: 'flex', justifyContent: 'flex-end', gap: 2, mt: 2 }}>
                          {editMode ? (
                            <>
                              <Button 
                                variant="outlined" 
                                onClick={handleEditToggle}
                                startIcon={<CancelIcon />}
                              >
                                {t('button.cancel')}
                              </Button>
                              
                              <Button 
                                type="submit" 
                                variant="contained"
                                color="primary"
                                disabled={saving}
                                startIcon={saving ? <CircularProgress size={20} /> : <SaveIcon />}
                              >
                                {saving ? t('button.saving') : t('button.save')}
                              </Button>
                            </>
                          ) : (
                            <Button 
                              variant="contained" 
                              color="primary" 
                              onClick={handleEditToggle}
                              startIcon={<EditIcon />}
                            >
                              {t('button.edit')}
                            </Button>
                          )}
                        </Box>
                      </Grid>
                    </Grid>
                  </form>
                </TabPanel>
                
                <TabPanel value={tabValue} index={1}>
                  <PasswordChangeForm />
                </TabPanel>
                
                <TabPanel value={tabValue} index={2}>
                  <NotificationPreferences />
                </TabPanel>
              </Card>
            </Grid>
          </Grid>
        </Box>
      </Fade>
    </DashboardLayout>
  );
};

export default ProfilePage;