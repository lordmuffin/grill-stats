import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import {
  Avatar,
  Box,
  Divider,
  IconButton,
  ListItemIcon,
  Menu,
  MenuItem,
  Tooltip,
  Typography,
  Zoom,
} from '@mui/material';
import AccountCircleIcon from '@mui/icons-material/AccountCircle';
import SettingsIcon from '@mui/icons-material/Settings';
import PermIdentityIcon from '@mui/icons-material/PermIdentity';
import LogoutButton from '@/components/auth/LogoutButton';
import type { User } from '@/types';

interface UserMenuProps {
  user: User | null;
}

/**
 * Enhanced user menu with account options and logout
 */
const UserMenu = ({ user }: UserMenuProps) => {
  const { t } = useTranslation();
  const navigate = useNavigate();
  
  const [anchorEl, setAnchorEl] = useState<null | HTMLElement>(null);
  const open = Boolean(anchorEl);
  
  const handleClick = (event: React.MouseEvent<HTMLElement>) => {
    setAnchorEl(event.currentTarget);
  };
  
  const handleClose = () => {
    setAnchorEl(null);
  };
  
  // Generate user initials for avatar
  const getUserInitials = () => {
    if (!user) return '?';
    
    if (user.firstName && user.lastName) {
      return `${user.firstName[0]}${user.lastName[0]}`.toUpperCase();
    }
    
    if (user.email) {
      return user.email[0].toUpperCase();
    }
    
    return '?';
  };
  
  return (
    <>
      <Tooltip 
        title={t('nav.profile')}
        arrow
        TransitionComponent={Zoom}
      >
        <IconButton
          onClick={handleClick}
          size="small"
          aria-controls={open ? 'account-menu' : undefined}
          aria-haspopup="true"
          aria-expanded={open ? 'true' : undefined}
          sx={{ 
            ml: 1,
            transition: 'transform 0.2s',
            '&:hover': {
              transform: 'scale(1.1)',
            },
          }}
        >
          <Avatar 
            sx={{ 
              width: 32, 
              height: 32, 
              bgcolor: 'primary.main',
              boxShadow: '0 2px 4px rgba(0,0,0,0.1)',
            }}
          >
            {getUserInitials()}
          </Avatar>
        </IconButton>
      </Tooltip>
      
      <Menu
        anchorEl={anchorEl}
        id="account-menu"
        open={open}
        onClose={handleClose}
        transformOrigin={{ horizontal: 'right', vertical: 'top' }}
        anchorOrigin={{ horizontal: 'right', vertical: 'bottom' }}
        PaperProps={{
          sx: {
            width: 250,
            borderRadius: 2,
            mt: 1,
            boxShadow: '0 4px 20px rgba(0,0,0,0.15)',
            '& .MuiMenuItem-root': {
              borderRadius: 1,
              mx: 1,
              my: 0.5,
              px: 2,
            },
          }
        }}
      >
        <Box sx={{ px: 3, py: 1.5 }}>
          <Typography variant="subtitle1" fontWeight="medium">
            {user?.firstName ? `${user.firstName} ${user.lastName || ''}` : user?.email}
          </Typography>
          <Typography variant="body2" color="text.secondary">
            {user?.email}
          </Typography>
        </Box>
        
        <Divider sx={{ my: 1 }} />
        
        <MenuItem onClick={() => { handleClose(); navigate('/profile'); }}>
          <ListItemIcon>
            <AccountCircleIcon fontSize="small" color="primary" />
          </ListItemIcon>
          {t('nav.profile')}
        </MenuItem>
        
        <Divider sx={{ my: 1 }} />
        
        <Box sx={{ px: 1, py: 0.5 }}>
          <LogoutButton 
            variant="outlined" 
            color="error" 
            size="small" 
            fullWidth 
            showIcon={true}
          />
        </Box>
      </Menu>
    </>
  );
};

export default UserMenu;