import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { 
  Box, 
  TextField, 
  Button, 
  Grid, 
  CircularProgress, 
  Alert, 
  Paper, 
  Typography,
  InputAdornment,
  IconButton
} from '@mui/material';
import VpnKeyIcon from '@mui/icons-material/VpnKey';
import VisibilityIcon from '@mui/icons-material/Visibility';
import VisibilityOffIcon from '@mui/icons-material/VisibilityOff';
import useAlerts from '@/hooks/useAlerts';

/**
 * Form for changing user password with validation and security checks
 */
const PasswordChangeForm = () => {
  const { t } = useTranslation();
  const { showSuccess, showError } = useAlerts();
  
  const [formValues, setFormValues] = useState({
    currentPassword: '',
    newPassword: '',
    confirmPassword: '',
  });
  
  const [formErrors, setFormErrors] = useState({
    currentPassword: '',
    newPassword: '',
    confirmPassword: '',
  });
  
  const [loading, setLoading] = useState(false);
  const [success, setSuccess] = useState(false);
  const [showPasswords, setShowPasswords] = useState({
    currentPassword: false,
    newPassword: false,
    confirmPassword: false,
  });
  
  const handleInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const { name, value } = e.target;
    setFormValues({
      ...formValues,
      [name]: value,
    });
    
    // Clear error when user types
    if (formErrors[name as keyof typeof formErrors]) {
      setFormErrors({
        ...formErrors,
        [name]: '',
      });
    }
    
    // Clear success message when user starts typing again
    if (success) {
      setSuccess(false);
    }
  };
  
  const togglePasswordVisibility = (field: keyof typeof showPasswords) => {
    setShowPasswords({
      ...showPasswords,
      [field]: !showPasswords[field],
    });
  };
  
  const validateForm = () => {
    const errors = {
      currentPassword: '',
      newPassword: '',
      confirmPassword: '',
    };
    let isValid = true;
    
    // Current password validation
    if (!formValues.currentPassword) {
      errors.currentPassword = t('validation.required');
      isValid = false;
    }
    
    // New password validation
    if (!formValues.newPassword) {
      errors.newPassword = t('validation.required');
      isValid = false;
    } else if (formValues.newPassword.length < 8) {
      errors.newPassword = t('validation.passwordLength');
      isValid = false;
    } else if (!/(?=.*\d)(?=.*[a-z])(?=.*[A-Z])/.test(formValues.newPassword)) {
      errors.newPassword = t('validation.passwordStrength');
      isValid = false;
    } else if (formValues.newPassword === formValues.currentPassword) {
      errors.newPassword = t('validation.passwordSame');
      isValid = false;
    }
    
    // Confirm password validation
    if (formValues.newPassword !== formValues.confirmPassword) {
      errors.confirmPassword = t('validation.passwordMatch');
      isValid = false;
    }
    
    setFormErrors(errors);
    return isValid;
  };
  
  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    
    if (!validateForm()) {
      return;
    }
    
    setLoading(true);
    
    try {
      // Here we would make the API call to change the password
      // For now, let's simulate it with a timeout
      await new Promise(resolve => setTimeout(resolve, 1500));
      
      // Show success message
      setSuccess(true);
      showSuccess(t('profile.passwordChangeSuccess'));
      
      // Reset form
      setFormValues({
        currentPassword: '',
        newPassword: '',
        confirmPassword: '',
      });
    } catch (error) {
      showError(t('profile.passwordChangeError'));
    } finally {
      setLoading(false);
    }
  };
  
  return (
    <Box component="form" onSubmit={handleSubmit} noValidate>
      <Grid container spacing={3}>
        <Grid item xs={12}>
          <Paper 
            elevation={0} 
            sx={{ 
              p: 2, 
              mb: 3, 
              bgcolor: 'background.default',
              border: '1px solid',
              borderColor: 'divider',
              borderRadius: 2
            }}
          >
            <Box sx={{ display: 'flex', alignItems: 'center', mb: 1 }}>
              <VpnKeyIcon color="primary" sx={{ mr: 1 }} />
              <Typography variant="h6">{t('profile.changePassword')}</Typography>
            </Box>
            <Typography variant="body2" color="text.secondary">
              {t('profile.passwordRequirements')}
            </Typography>
          </Paper>
        </Grid>
        
        <Grid item xs={12}>
          <TextField
            fullWidth
            label={t('profile.currentPassword')}
            name="currentPassword"
            type={showPasswords.currentPassword ? 'text' : 'password'}
            value={formValues.currentPassword}
            onChange={handleInputChange}
            error={!!formErrors.currentPassword}
            helperText={formErrors.currentPassword}
            required
            InputProps={{
              endAdornment: (
                <InputAdornment position="end">
                  <IconButton
                    edge="end"
                    onClick={() => togglePasswordVisibility('currentPassword')}
                  >
                    {showPasswords.currentPassword ? <VisibilityOffIcon /> : <VisibilityIcon />}
                  </IconButton>
                </InputAdornment>
              ),
            }}
          />
        </Grid>
        
        <Grid item xs={12}>
          <TextField
            fullWidth
            label={t('profile.newPassword')}
            name="newPassword"
            type={showPasswords.newPassword ? 'text' : 'password'}
            value={formValues.newPassword}
            onChange={handleInputChange}
            error={!!formErrors.newPassword}
            helperText={formErrors.newPassword}
            required
            InputProps={{
              endAdornment: (
                <InputAdornment position="end">
                  <IconButton
                    edge="end"
                    onClick={() => togglePasswordVisibility('newPassword')}
                  >
                    {showPasswords.newPassword ? <VisibilityOffIcon /> : <VisibilityIcon />}
                  </IconButton>
                </InputAdornment>
              ),
            }}
          />
        </Grid>
        
        <Grid item xs={12}>
          <TextField
            fullWidth
            label={t('profile.confirmPassword')}
            name="confirmPassword"
            type={showPasswords.confirmPassword ? 'text' : 'password'}
            value={formValues.confirmPassword}
            onChange={handleInputChange}
            error={!!formErrors.confirmPassword}
            helperText={formErrors.confirmPassword}
            required
            InputProps={{
              endAdornment: (
                <InputAdornment position="end">
                  <IconButton
                    edge="end"
                    onClick={() => togglePasswordVisibility('confirmPassword')}
                  >
                    {showPasswords.confirmPassword ? <VisibilityOffIcon /> : <VisibilityIcon />}
                  </IconButton>
                </InputAdornment>
              ),
            }}
          />
        </Grid>
        
        {success && (
          <Grid item xs={12}>
            <Alert severity="success">
              {t('profile.passwordChangeSuccess')}
            </Alert>
          </Grid>
        )}
        
        <Grid item xs={12}>
          <Box sx={{ display: 'flex', justifyContent: 'flex-end' }}>
            <Button
              type="submit"
              variant="contained"
              color="primary"
              disabled={loading}
              startIcon={loading && <CircularProgress size={20} />}
              sx={{ mt: 2 }}
            >
              {loading ? t('button.saving') : t('profile.updatePassword')}
            </Button>
          </Box>
        </Grid>
      </Grid>
    </Box>
  );
};

export default PasswordChangeForm;