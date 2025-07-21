import { ReactNode } from 'react';
import { Box, Container, Toolbar } from '@mui/material';
import Header from './Header';
import Sidebar from './Sidebar';
import AlertNotifications from '../common/AlertNotifications';
import { useAppSelector } from '@/hooks/reduxHooks';
import { selectDrawerOpen } from '@/store/slices/uiSlice';
import useResponsive from '@/hooks/useResponsive';

interface MainLayoutProps {
  children: ReactNode;
}

const DRAWER_WIDTH = 240;

/**
 * Main application layout with header, sidebar, and content area
 */
const MainLayout = ({ children }: MainLayoutProps) => {
  const drawerOpen = useAppSelector(selectDrawerOpen);
  const isMobile = useResponsive();
  
  return (
    <Box sx={{ display: 'flex', minHeight: '100vh' }}>
      {/* App Bar */}
      <Header />
      
      {/* Sidebar */}
      <Sidebar />
      
      {/* Main Content */}
      <Box
        component="main"
        sx={{
          flexGrow: 1,
          overflow: 'auto',
          transition: (theme) => theme.transitions.create('margin', {
            easing: theme.transitions.easing.sharp,
            duration: theme.transitions.duration.leavingScreen,
          }),
          ml: { md: `${DRAWER_WIDTH}px` },
          width: { 
            xs: '100%',
            md: `calc(100% - ${DRAWER_WIDTH}px)`,
          },
          ...(!isMobile && !drawerOpen && {
            ml: '0',
            width: '100%',
          }),
        }}
      >
        <Toolbar /> {/* Offset for fixed app bar */}
        <Container maxWidth="xl" sx={{ py: 4 }}>
          {children}
        </Container>
      </Box>
      
      {/* Alert Notifications */}
      <AlertNotifications />
    </Box>
  );
};

export default MainLayout;