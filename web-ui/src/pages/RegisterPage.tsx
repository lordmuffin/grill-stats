import { Box, Container, Paper, Typography } from '@mui/material';
import RegisterForm from '@/components/auth/RegisterForm';

/**
 * Registration page
 */
const RegisterPage = () => {
  return (
    <Box
      sx={{
        display: 'flex',
        minHeight: '100vh',
        alignItems: 'center',
        backgroundColor: (theme) => theme.palette.background.default,
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
            Create Account
          </Typography>
          <Typography variant="subtitle1" color="text.secondary">
            Join Grill Stats and start monitoring your temperatures
          </Typography>
        </Box>
        
        <RegisterForm />
        
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
            &copy; {new Date().getFullYear()} Grill Stats. All rights reserved.
          </Typography>
        </Paper>
      </Container>
    </Box>
  );
};

export default RegisterPage;