import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { 
  Button, 
  CircularProgress, 
  Dialog, 
  DialogActions, 
  DialogContent, 
  DialogContentText, 
  DialogTitle,
  IconButton,
  Tooltip,
  Zoom,
  Fade
} from '@mui/material';
import LogoutIcon from '@mui/icons-material/Logout';
import ExitToAppIcon from '@mui/icons-material/ExitToApp';
import { useAppDispatch, useAppSelector } from '@/hooks/reduxHooks';
import { logout, selectAuthLoading } from '@/store/slices/authSlice';
import useAlerts from '@/hooks/useAlerts';

interface LogoutButtonProps {
  variant?: 'text' | 'outlined' | 'contained';
  color?: 'inherit' | 'primary' | 'secondary' | 'error';
  size?: 'small' | 'medium' | 'large';
  showIcon?: boolean;
  fullWidth?: boolean;
  iconOnly?: boolean;
}

/**
 * Enhanced logout button with confirmation dialog and i18n support
 */
const LogoutButton = ({
  variant = 'text',
  color = 'inherit',
  size = 'medium',
  showIcon = true,
  fullWidth = false,
  iconOnly = false,
}: LogoutButtonProps) => {
  const { t } = useTranslation();
  const dispatch = useAppDispatch();
  const navigate = useNavigate();
  const { showError, showSuccess } = useAlerts();
  const isLoading = useAppSelector(selectAuthLoading);
  
  const [confirmOpen, setConfirmOpen] = useState(false);
  
  const handleLogout = async () => {
    setConfirmOpen(false);
    
    try {
      await dispatch(logout()).unwrap();
      showSuccess(t('success.logout'));
      navigate('/login');
    } catch (error) {
      showError(`${t('error.general')}: ${error instanceof Error ? error.message : t('error.general')}`);
    }
  };
  
  // Icon-only version (for small screens or user menu)
  if (iconOnly) {
    return (
      <>
        <Tooltip 
          title={t('auth.logout')} 
          placement="bottom" 
          arrow 
          TransitionComponent={Zoom}
        >
          <IconButton
            color={color}
            size={size}
            onClick={() => setConfirmOpen(true)}
            disabled={isLoading}
            aria-label={t('auth.logout')}
          >
            {isLoading ? <CircularProgress size={24} /> : <ExitToAppIcon />}
          </IconButton>
        </Tooltip>
        
        <LogoutConfirmDialog
          open={confirmOpen}
          onClose={() => setConfirmOpen(false)}
          onConfirm={handleLogout}
          isLoading={isLoading}
        />
      </>
    );
  }
  
  // Regular button version
  return (
    <>
      <Button
        variant={variant}
        color={color}
        size={size}
        onClick={() => setConfirmOpen(true)}
        startIcon={showIcon ? <LogoutIcon /> : undefined}
        fullWidth={fullWidth}
        disabled={isLoading}
        sx={{ 
          borderRadius: 2,
          transition: 'all 0.2s ease',
          '&:hover': {
            transform: 'translateY(-2px)',
            boxShadow: '0 4px 8px rgba(0,0,0,0.1)'
          }
        }}
      >
        {isLoading ? (
          <CircularProgress size={24} color="inherit" />
        ) : (
          t('auth.logout')
        )}
      </Button>
      
      <LogoutConfirmDialog
        open={confirmOpen}
        onClose={() => setConfirmOpen(false)}
        onConfirm={handleLogout}
        isLoading={isLoading}
      />
    </>
  );
};

interface LogoutConfirmDialogProps {
  open: boolean;
  onClose: () => void;
  onConfirm: () => void;
  isLoading: boolean;
}

/**
 * Enhanced logout confirmation dialog
 */
const LogoutConfirmDialog = ({
  open,
  onClose,
  onConfirm,
  isLoading
}: LogoutConfirmDialogProps) => {
  const { t } = useTranslation();
  
  return (
    <Dialog
      open={open}
      onClose={onClose}
      aria-labelledby="logout-dialog-title"
      aria-describedby="logout-dialog-description"
      TransitionComponent={Fade}
      PaperProps={{
        elevation: 4,
        sx: {
          borderRadius: 2,
          maxWidth: 'sm',
          minWidth: { xs: '80%', sm: 400 },
        }
      }}
    >
      <DialogTitle id="logout-dialog-title" sx={{ pb: 1 }}>
        {t('auth.logout')}
      </DialogTitle>
      <DialogContent>
        <DialogContentText id="logout-dialog-description">
          Are you sure you want to log out of your account? Your session will be ended.
        </DialogContentText>
      </DialogContent>
      <DialogActions sx={{ px: 3, pb: 2 }}>
        <Button 
          onClick={onClose} 
          color="primary"
          variant="outlined"
          disabled={isLoading}
          sx={{ borderRadius: 2 }}
        >
          {t('button.cancel')}
        </Button>
        <Button 
          onClick={onConfirm} 
          color="error" 
          variant="contained"
          autoFocus
          disabled={isLoading}
          startIcon={isLoading ? <CircularProgress size={16} /> : <LogoutIcon />}
          sx={{ borderRadius: 2 }}
        >
          {t('auth.logout')}
        </Button>
      </DialogActions>
    </Dialog>
  );
};

export default LogoutButton;