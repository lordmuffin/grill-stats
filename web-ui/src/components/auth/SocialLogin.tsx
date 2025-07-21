import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { 
  Box, 
  Button, 
  Divider, 
  Typography, 
  Stack,
  CircularProgress,
  useTheme
} from '@mui/material';
import GoogleIcon from '@mui/icons-material/Google';
import FacebookIcon from '@mui/icons-material/Facebook';
import GitHubIcon from '@mui/icons-material/GitHub';
import TwitterIcon from '@mui/icons-material/Twitter';
import { useAppDispatch } from '@/hooks/reduxHooks';
import useAlerts from '@/hooks/useAlerts';
import { api } from '@/store/api';

/**
 * Component for OAuth2 social login options
 */
const SocialLogin = () => {
  const { t } = useTranslation();
  const theme = useTheme();
  const dispatch = useAppDispatch();
  const { showError } = useAlerts();
  
  const [loadingProvider, setLoadingProvider] = useState<string | null>(null);
  
  // Handle social login
  const handleSocialLogin = async (provider: string) => {
    setLoadingProvider(provider);
    
    try {
      // In a real implementation, we'd redirect to the OAuth provider
      // For now, let's simulate the process with a timeout
      await new Promise(resolve => setTimeout(resolve, 1500));
      
      // Mock the OAuth flow
      window.open(`${import.meta.env.VITE_API_BASE_URL}/auth/${provider}`, '_self');
      
      // In reality, we would:
      // 1. Redirect to OAuth provider
      // 2. Handle the callback with a token
      // 3. Exchange the token for user data
      // 4. Set the auth state
      
    } catch (error) {
      showError(t('auth.socialLoginError', { provider }));
      console.error(`Social login error (${provider}):`, error);
    } finally {
      setLoadingProvider(null);
    }
  };
  
  return (
    <Box sx={{ width: '100%', mt: 3, mb: 2 }}>
      <Divider>
        <Typography 
          variant="body2" 
          color="text.secondary"
          sx={{ px: 2, fontWeight: 500 }}
        >
          {t('auth.orContinueWith')}
        </Typography>
      </Divider>
      
      <Stack 
        direction="row" 
        spacing={2} 
        sx={{ 
          mt: 3,
          justifyContent: 'center',
          flexWrap: 'wrap',
          gap: 2
        }}
      >
        <Button
          variant="outlined"
          startIcon={loadingProvider === 'google' ? <CircularProgress size={20} /> : <GoogleIcon />}
          onClick={() => handleSocialLogin('google')}
          disabled={!!loadingProvider}
          sx={{
            borderRadius: 2,
            borderColor: theme.palette.mode === 'dark' ? 'rgba(255, 255, 255, 0.15)' : 'rgba(0, 0, 0, 0.15)',
            color: theme.palette.mode === 'dark' ? 'rgba(255, 255, 255, 0.9)' : 'rgba(0, 0, 0, 0.8)',
            backgroundColor: theme.palette.mode === 'dark' ? 'rgba(255, 255, 255, 0.05)' : 'rgba(0, 0, 0, 0.01)',
            px: 2,
            minWidth: 110,
            '&:hover': {
              borderColor: theme.palette.mode === 'dark' ? 'rgba(255, 255, 255, 0.3)' : 'rgba(0, 0, 0, 0.3)',
              backgroundColor: theme.palette.mode === 'dark' ? 'rgba(255, 255, 255, 0.1)' : 'rgba(0, 0, 0, 0.03)',
            }
          }}
        >
          {loadingProvider === 'google' ? t('auth.connecting') : 'Google'}
        </Button>
        
        <Button
          variant="outlined"
          startIcon={loadingProvider === 'facebook' ? <CircularProgress size={20} /> : <FacebookIcon />}
          onClick={() => handleSocialLogin('facebook')}
          disabled={!!loadingProvider}
          sx={{
            borderRadius: 2,
            borderColor: theme.palette.mode === 'dark' ? 'rgba(255, 255, 255, 0.15)' : 'rgba(0, 0, 0, 0.15)',
            color: theme.palette.mode === 'dark' ? 'rgba(255, 255, 255, 0.9)' : 'rgba(0, 0, 0, 0.8)',
            backgroundColor: theme.palette.mode === 'dark' ? 'rgba(255, 255, 255, 0.05)' : 'rgba(0, 0, 0, 0.01)',
            px: 2,
            minWidth: 110,
            '&:hover': {
              borderColor: theme.palette.mode === 'dark' ? 'rgba(255, 255, 255, 0.3)' : 'rgba(0, 0, 0, 0.3)',
              backgroundColor: theme.palette.mode === 'dark' ? 'rgba(255, 255, 255, 0.1)' : 'rgba(0, 0, 0, 0.03)',
            }
          }}
        >
          {loadingProvider === 'facebook' ? t('auth.connecting') : 'Facebook'}
        </Button>
        
        <Button
          variant="outlined"
          startIcon={loadingProvider === 'github' ? <CircularProgress size={20} /> : <GitHubIcon />}
          onClick={() => handleSocialLogin('github')}
          disabled={!!loadingProvider}
          sx={{
            borderRadius: 2,
            borderColor: theme.palette.mode === 'dark' ? 'rgba(255, 255, 255, 0.15)' : 'rgba(0, 0, 0, 0.15)',
            color: theme.palette.mode === 'dark' ? 'rgba(255, 255, 255, 0.9)' : 'rgba(0, 0, 0, 0.8)',
            backgroundColor: theme.palette.mode === 'dark' ? 'rgba(255, 255, 255, 0.05)' : 'rgba(0, 0, 0, 0.01)',
            px: 2,
            minWidth: 110,
            '&:hover': {
              borderColor: theme.palette.mode === 'dark' ? 'rgba(255, 255, 255, 0.3)' : 'rgba(0, 0, 0, 0.3)',
              backgroundColor: theme.palette.mode === 'dark' ? 'rgba(255, 255, 255, 0.1)' : 'rgba(0, 0, 0, 0.03)',
            }
          }}
        >
          {loadingProvider === 'github' ? t('auth.connecting') : 'GitHub'}
        </Button>
      </Stack>
      
      <Typography 
        variant="caption" 
        color="text.secondary" 
        align="center" 
        sx={{ 
          display: 'block', 
          mt: 2,
          px: 2,
          opacity: 0.7
        }}
      >
        {t('auth.socialLoginDisclaimer')}
      </Typography>
    </Box>
  );
};

export default SocialLogin;