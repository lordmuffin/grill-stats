import { AppBar, Box, IconButton, Toolbar, Typography, Badge, useMediaQuery, useTheme } from '@mui/material';
import MenuIcon from '@mui/icons-material/Menu';
import NotificationsIcon from '@mui/icons-material/Notifications';
import { useTranslation } from 'react-i18next';
import { useAppDispatch, useAppSelector } from '@/hooks/reduxHooks';
import { toggleDrawer } from '@/store/slices/uiSlice';
import { selectAlerts, toggleNotifications } from '@/store/slices/uiSlice';
import { selectUser } from '@/store/slices/authSlice';
import ThemeToggle from '../common/ThemeToggle';
import LanguageSelector from '../common/LanguageSelector';
import UserMenu from './UserMenu';

const DRAWER_WIDTH = 240;

/**
 * Application header with navigation and user controls
 */
const Header = () => {
  const dispatch = useAppDispatch();
  const user = useAppSelector(selectUser);
  const alerts = useAppSelector(selectAlerts);
  const theme = useTheme();
  const isMobile = useMediaQuery(theme.breakpoints.down('md'));
  const { t } = useTranslation();
  
  // Count unacknowledged alerts
  const unacknowledgedAlerts = alerts.length;
  
  const handleDrawerToggle = () => {
    dispatch(toggleDrawer());
  };
  
  const handleNotificationsToggle = () => {
    dispatch(toggleNotifications());
  };
  
  return (
    <AppBar
      position="fixed"
      sx={{
        zIndex: (theme) => theme.zIndex.drawer + 1,
        transition: theme.transitions.create(['width', 'margin'], {
          easing: theme.transitions.easing.sharp,
          duration: theme.transitions.duration.leavingScreen,
        }),
        ...(isMobile && {
          width: '100%',
        }),
        ...(!isMobile && {
          width: `calc(100% - ${DRAWER_WIDTH}px)`,
          ml: `${DRAWER_WIDTH}px`,
        }),
      }}
    >
      <Toolbar>
        {isMobile && (
          <IconButton
            color="inherit"
            aria-label="open drawer"
            edge="start"
            onClick={handleDrawerToggle}
            sx={{ mr: 2 }}
          >
            <MenuIcon />
          </IconButton>
        )}
        
        <Typography
          variant="h6"
          component="div"
          sx={{ flexGrow: 1, display: { xs: 'none', sm: 'block' } }}
        >
          {t('app.name')}
        </Typography>
        
        <Box sx={{ display: 'flex', alignItems: 'center' }}>
          {/* Notifications */}
          <IconButton color="inherit" onClick={handleNotificationsToggle}>
            <Badge badgeContent={unacknowledgedAlerts} color="error">
              <NotificationsIcon />
            </Badge>
          </IconButton>
          
          {/* Language Selector */}
          <LanguageSelector />
          
          {/* Theme Toggle */}
          <ThemeToggle />
          
          {/* User Menu */}
          <UserMenu user={user} />
        </Box>
      </Toolbar>
    </AppBar>
  );
};

export default Header;