import { useState, useEffect } from 'react';
import { Link as RouterLink, useNavigate } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import {
  Box,
  Button,
  Checkbox,
  FormControlLabel,
  TextField,
  Typography,
  Link,
  CircularProgress,
  Alert,
  Paper,
  InputAdornment,
  IconButton,
  Slide,
  Tooltip,
  Zoom
} from '@mui/material';
import EmailIcon from '@mui/icons-material/Email';
import LockIcon from '@mui/icons-material/Lock';
import Visibility from '@mui/icons-material/Visibility';
import VisibilityOff from '@mui/icons-material/VisibilityOff';
import InfoIcon from '@mui/icons-material/Info';
import { useAppDispatch, useAppSelector } from '@/hooks/reduxHooks';
import { login, selectAuthLoading, selectAuthError, clearError, selectIsAuthenticated } from '@/store/slices/authSlice';
import SocialLogin from './SocialLogin';

/**
 * Enhanced login form with animations and better validation
 */
const LoginForm = () => {
  const { t } = useTranslation();
  const dispatch = useAppDispatch();
  const navigate = useNavigate();
  const isLoading = useAppSelector(selectAuthLoading);
  const error = useAppSelector(selectAuthError);
  const isAuthenticated = useAppSelector(selectIsAuthenticated);

  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [rememberMe, setRememberMe] = useState(true);
  const [showPassword, setShowPassword] = useState(false);
  const [formReady, setFormReady] = useState(false);

  // Validation states
  const [emailError, setEmailError] = useState('');
  const [passwordError, setPasswordError] = useState('');
  const [emailTouched, setEmailTouched] = useState(false);
  const [passwordTouched, setPasswordTouched] = useState(false);

  // Redirect if already authenticated
  useEffect(() => {
    if (isAuthenticated) {
      navigate('/dashboard');
    }
  }, [isAuthenticated, navigate]);

  // Animation on mount
  useEffect(() => {
    setFormReady(true);
  }, []);

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

  const validatePassword = (value: string) => {
    if (!value) {
      setPasswordError(t('error.requiredField'));
      return false;
    } else if (value.length < 6) {
      setPasswordError(t('auth.passwordRequirements'));
      return false;
    } else {
      setPasswordError('');
      return true;
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    
    // Mark fields as touched for validation
    setEmailTouched(true);
    setPasswordTouched(true);
    
    // Clear any previous errors
    dispatch(clearError());
    
    // Validate inputs
    const isEmailValid = validateEmail(email);
    const isPasswordValid = validatePassword(password);
    
    if (!isEmailValid || !isPasswordValid) {
      return;
    }
    
    // Dispatch login action
    dispatch(login({ email, password, rememberMe }));
  };

  const handleTogglePasswordVisibility = () => {
    setShowPassword((prev) => !prev);
  };

  return (
    <Slide direction="up" in={formReady} mountOnEnter unmountOnExit>
      <Paper
        elevation={3}
        sx={{
          p: { xs: 3, sm: 4 },
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
            background: (theme) => 
              `linear-gradient(to right, ${theme.palette.primary.main}, ${theme.palette.secondary.main})`,
          },
        }}
      >
        <Box component="form" onSubmit={handleSubmit} noValidate>
          <Typography 
            component="h1" 
            variant="h5" 
            align="center" 
            fontWeight="bold"
            color="primary"
            gutterBottom
          >
            {t('auth.login')}
          </Typography>
          
          {error && (
            <Alert 
              severity="error" 
              sx={{ 
                mb: 3, 
                mt: 2,
                borderRadius: 2,
                animation: 'pulse 1.5s infinite',
                '@keyframes pulse': {
                  '0%': { opacity: 1 },
                  '50%': { opacity: 0.85 },
                  '100%': { opacity: 1 },
                }
              }}
            >
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
          
          <TextField
            margin="normal"
            required
            fullWidth
            name="password"
            label={t('auth.password')}
            type={showPassword ? 'text' : 'password'}
            id="password"
            autoComplete="current-password"
            value={password}
            onChange={(e) => {
              setPassword(e.target.value);
              if (passwordTouched) validatePassword(e.target.value);
            }}
            onBlur={() => {
              setPasswordTouched(true);
              validatePassword(password);
            }}
            error={passwordTouched && !!passwordError}
            helperText={passwordTouched && passwordError}
            disabled={isLoading}
            InputProps={{
              startAdornment: (
                <InputAdornment position="start">
                  <LockIcon color={passwordTouched && passwordError ? "error" : "action"} />
                </InputAdornment>
              ),
              endAdornment: (
                <InputAdornment position="end">
                  <IconButton
                    aria-label="toggle password visibility"
                    onClick={handleTogglePasswordVisibility}
                    edge="end"
                  >
                    {showPassword ? <VisibilityOff /> : <Visibility />}
                  </IconButton>
                </InputAdornment>
              ),
            }}
            sx={{
              '& .MuiOutlinedInput-root': {
                borderRadius: 2,
              }
            }}
          />
          
          <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mt: 1 }}>
            <FormControlLabel
              control={
                <Checkbox
                  value="remember"
                  color="primary"
                  checked={rememberMe}
                  onChange={(e) => setRememberMe(e.target.checked)}
                  disabled={isLoading}
                  sx={{ '& .MuiSvgIcon-root': { fontSize: 20 } }}
                />
              }
              label={
                <Typography variant="body2">{t('auth.rememberMe')}</Typography>
              }
            />
            
            <Tooltip 
              title={t('auth.forgotPassword')} 
              TransitionComponent={Zoom} 
              arrow
              placement="top"
            >
              <Link 
                component={RouterLink} 
                to="/forgot-password" 
                variant="body2" 
                color="primary"
                sx={{ 
                  display: 'flex', 
                  alignItems: 'center',
                  textDecoration: 'none',
                  '&:hover': { textDecoration: 'underline' }
                }}
              >
                <InfoIcon fontSize="small" sx={{ mr: 0.5 }} />
                {t('auth.forgotPassword')}
              </Link>
            </Tooltip>
          </Box>
          
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
              boxShadow: '0 4px 10px rgba(244, 67, 54, 0.25)',
              '&:hover': {
                boxShadow: '0 6px 15px rgba(244, 67, 54, 0.35)',
              },
              position: 'relative',
              overflow: 'hidden',
            }}
            disabled={isLoading}
          >
            {isLoading ? (
              <CircularProgress size={26} color="inherit" />
            ) : (
              t('auth.login')
            )}
          </Button>
          
          <SocialLogin />
          
          <Box sx={{ textAlign: 'center', mt: 2 }}>
            <Typography variant="body2" color="text.secondary">
              {t('auth.noAccount')}{' '}
              <Link 
                component={RouterLink} 
                to="/register" 
                variant="body2" 
                sx={{ fontWeight: 'medium' }}
              >
                {t('auth.signUp')}
              </Link>
            </Typography>
          </Box>
        </Box>
      </Paper>
    </Slide>
  );
};

export default LoginForm;