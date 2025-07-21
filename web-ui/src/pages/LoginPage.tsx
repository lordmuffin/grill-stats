import { useState, useEffect } from 'react';
import { Link as RouterLink } from 'react-router-dom';
import { 
  Box, 
  Container, 
  Paper, 
  Typography, 
  Grid, 
  Link,
  Card,
  CardMedia,
  useMediaQuery,
  useTheme,
  Fade,
  Divider
} from '@mui/material';
import { useTranslation } from 'react-i18next';
import LoginForm from '@/components/auth/LoginForm';

/**
 * Enhanced login page with animated background and better layout
 */
const LoginPage = () => {
  const { t } = useTranslation();
  const theme = useTheme();
  const isMobile = useMediaQuery(theme.breakpoints.down('md'));
  const [loaded, setLoaded] = useState(false);
  
  // Animation effect on load
  useEffect(() => {
    setLoaded(true);
  }, []);
  
  return (
    <Box
      sx={{
        display: 'flex',
        minHeight: '100vh',
        alignItems: 'center',
        backgroundImage: theme.palette.mode === 'dark' 
          ? 'linear-gradient(to bottom right, #121212, #2d2d2d)'
          : 'linear-gradient(to bottom right, #f5f5f5, #e0e0e0)',
      }}
    >
      <Container maxWidth="lg">
        <Fade in={loaded} timeout={1000}>
          <Grid container spacing={3} alignItems="center" justifyContent="center">
            {/* Left side - Image and branding for desktop */}
            {!isMobile && (
              <Grid item xs={12} md={6} lg={7}>
                <Box sx={{ p: 2, textAlign: 'center' }}>
                  <Card 
                    elevation={4}
                    sx={{ 
                      borderRadius: 3, 
                      overflow: 'hidden',
                      boxShadow: '0 10px 30px rgba(0, 0, 0, 0.1)',
                    }}
                  >
                    <CardMedia
                      component="img"
                      alt="Grill Monitoring"
                      height="400"
                      image="https://images.unsplash.com/photo-1555939594-58d7cb561ad1?q=80&w=2787&auto=format&fit=crop"
                      sx={{
                        objectFit: 'cover',
                        transition: 'transform 0.3s ease-in-out',
                        '&:hover': {
                          transform: 'scale(1.05)',
                        },
                      }}
                    />
                  </Card>
                  <Typography 
                    variant="h3" 
                    component="h1" 
                    color="primary" 
                    fontWeight="bold"
                    sx={{ mt: 4, mb: 1 }}
                  >
                    {t('app.name')}
                  </Typography>
                  <Typography 
                    variant="h6" 
                    color="text.secondary"
                    sx={{ maxWidth: '80%', mx: 'auto' }}
                  >
                    {t('app.tagline')}
                  </Typography>
                </Box>
              </Grid>
            )}
            
            {/* Right side - Login form */}
            <Grid item xs={12} md={6} lg={5}>
              <Box sx={{ textAlign: 'center', mb: 4 }}>
                {isMobile && (
                  <>
                    <Typography 
                      variant="h4" 
                      component="h1" 
                      color="primary" 
                      fontWeight="bold"
                      gutterBottom
                    >
                      {t('app.name')}
                    </Typography>
                    <Typography variant="subtitle1" color="text.secondary" sx={{ mb: 4 }}>
                      {t('app.tagline')}
                    </Typography>
                  </>
                )}
              </Box>
              
              <LoginForm />
              
              <Paper 
                elevation={0} 
                sx={{ 
                  mt: 4, 
                  p: 2, 
                  textAlign: 'center',
                  backgroundColor: 'transparent',
                }}
              >
                <Divider sx={{ my: 2 }} />
                
                <Box sx={{ mt: 2, mb: 1 }}>
                  <Link component={RouterLink} to="/register" variant="body2" color="primary">
                    {t('auth.dontHaveAccount')}
                  </Link>
                </Box>
                
                <Typography variant="body2" color="text.secondary" sx={{ mt: 3 }}>
                  {t('app.copyright', { year: new Date().getFullYear() })}
                </Typography>
              </Paper>
            </Grid>
          </Grid>
        </Fade>
      </Container>
    </Box>
  );
};

export default LoginPage;