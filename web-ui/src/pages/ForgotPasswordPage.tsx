import { useState } from 'react';
import { Link as RouterLink } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { 
  Box, 
  Container, 
  Paper, 
  Typography, 
  TextField,
  Button,
  Link,
  Alert,
  InputAdornment,
  CircularProgress,
  Divider
} from '@mui/material';
import EmailIcon from '@mui/icons-material/Email';
import ArrowBackIcon from '@mui/icons-material/ArrowBack';

/**
 * Password reset request page
 */
const ForgotPasswordPage = () => {
  const { t } = useTranslation();
  const [email, setEmail] = useState('');
  const [emailError, setEmailError] = useState('');
  const [emailTouched, setEmailTouched] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const [isSuccess, setIsSuccess] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const validateEmail = (value: string) => {
    const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
    if (!value) {
      setEmailError(t('error.requiredField'));
      return false;
    } else if (!emailRegex.test(value)) {
      setEmailError(t('error.invalidEmail'));
      return false;
    } else {
      setEmailError('');
      return true;
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    
    // Mark field as touched for validation
    setEmailTouched(true);
    
    // Validate email
    const isEmailValid = validateEmail(email);
    if (!isEmailValid) {
      return;
    }
    
    // Clear previous errors
    setError(null);
    
    // Show loading state
    setIsLoading(true);
    
    try {
      // Simulate API call for password reset
      await new Promise(resolve => setTimeout(resolve, 1500));
      
      // For demo purposes, always succeed
      setIsSuccess(true);
    } catch (err) {
      setError(t('error.general'));
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <Box
      sx={{
        display: 'flex',
        minHeight: '100vh',
        alignItems: 'center',
        backgroundImage: theme => 
          theme.palette.mode === 'dark' 
            ? 'linear-gradient(to bottom right, #121212, #2d2d2d)'
            : 'linear-gradient(to bottom right, #f5f5f5, #e0e0e0)',
      }}
    >
      <Container maxWidth="sm">
        <Box sx={{ mb: 4, textAlign: 'center' }}>
          <Typography 
            variant="h4" 
            component="h1" 
            color="primary" 
            fontWeight="bold"
            gutterBottom
          >
            {t('app.name')}
          </Typography>
          <Typography variant="subtitle1" color="text.secondary">
            {t('app.tagline')}
          </Typography>
        </Box>
        
        <Paper
          elevation={3}
          sx={{
            p: 4,
            width: '100%',
            maxWidth: 450,
            mx: 'auto',
            borderRadius: 3,
            boxShadow: '0 8px 24px rgba(0, 0, 0, 0.12)',
            position: 'relative',
            overflow: 'hidden',
            '&::before': {
              content: '""',
              position: 'absolute',
              top: 0,
              left: 0,
              width: '100%',
              height: '4px',
              background: theme => 
                `linear-gradient(to right, ${theme.palette.primary.main}, ${theme.palette.secondary.main})`,
            },
          }}
        >
          {!isSuccess ? (
            <Box component="form" onSubmit={handleSubmit} noValidate>
              <Typography 
                component="h1" 
                variant="h5" 
                align="center" 
                fontWeight="bold"
                color="primary"
                gutterBottom
              >
                {t('auth.forgotPassword')}
              </Typography>
              
              <Typography variant="body1" color="text.secondary" align="center" sx={{ mb: 3 }}>
                {t('auth.resetPasswordInstructions')}
              </Typography>
              
              {error && (
                <Alert severity="error" sx={{ mb: 3 }}>
                  {error}
                </Alert>
              )}
              
              <TextField
                margin="normal"
                required
                fullWidth
                id="email"
                label={t('auth.email')}
                name="email"
                autoComplete="email"
                autoFocus
                value={email}
                onChange={(e) => {
                  setEmail(e.target.value);
                  if (emailTouched) validateEmail(e.target.value);
                }}
                onBlur={() => {
                  setEmailTouched(true);
                  validateEmail(email);
                }}
                error={emailTouched && !!emailError}
                helperText={emailTouched && emailError}
                disabled={isLoading}
                InputProps={{
                  startAdornment: (
                    <InputAdornment position="start">
                      <EmailIcon color={emailTouched && emailError ? "error" : "action"} />
                    </InputAdornment>
                  ),
                }}
                sx={{
                  '& .MuiOutlinedInput-root': {
                    borderRadius: 2,
                  }
                }}
              />
              
              <Button
                type="submit"
                fullWidth
                variant="contained"
                size="large"
                sx={{ 
                  mt: 3, 
                  mb: 2,
                  py: 1.5,
                  borderRadius: 2,
                }}
                disabled={isLoading}
              >
                {isLoading ? (
                  <CircularProgress size={24} color="inherit" />
                ) : (
                  t('button.sendLink')
                )}
              </Button>
            </Box>
          ) : (
            <Box sx={{ textAlign: 'center' }}>
              <Alert severity="success" sx={{ mb: 3 }}>
                {t('success.passwordReset')}
              </Alert>
              
              <Typography variant="body1" paragraph>
                Check your email inbox for instructions on how to reset your password.
              </Typography>
              
              <Typography variant="body2" color="text.secondary" paragraph>
                If you don't receive an email within a few minutes, please check your spam folder.
              </Typography>
            </Box>
          )}
          
          <Divider sx={{ my: 2 }} />
          
          <Box sx={{ textAlign: 'center', mt: 2 }}>
            <Link 
              component={RouterLink} 
              to="/login" 
              variant="body2"
              sx={{ 
                display: 'inline-flex', 
                alignItems: 'center',
                textDecoration: 'none',
                '&:hover': { textDecoration: 'underline' }
              }}
            >
              <ArrowBackIcon fontSize="small" sx={{ mr: 0.5 }} />
              {t('auth.login')}
            </Link>
          </Box>
        </Paper>
        
        <Paper 
          elevation={0} 
          sx={{ 
            mt: 4, 
            p: 2, 
            textAlign: 'center',
            backgroundColor: 'transparent',
          }}
        >
          <Typography variant="body2" color="text.secondary">
            {t('app.copyright', { year: new Date().getFullYear() })}
          </Typography>
        </Paper>
      </Container>
    </Box>
  );
};

export default ForgotPasswordPage;