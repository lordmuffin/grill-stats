import { useState } from 'react';
import { IconButton, Menu, MenuItem, Switch, Tooltip, Typography } from '@mui/material';
import Brightness4Icon from '@mui/icons-material/Brightness4';
import Brightness7Icon from '@mui/icons-material/Brightness7';
import { useAppDispatch, useAppSelector } from '@/hooks/reduxHooks';
import { selectThemeMode, selectUseSystemPreference, toggleThemeMode, setUseSystemPreference } from '@/store/slices/themeSlice';

/**
 * A button that toggles between light and dark themes
 */
const ThemeToggle = () => {
  const dispatch = useAppDispatch();
  const themeMode = useAppSelector(selectThemeMode);
  const useSystemPreference = useAppSelector(selectUseSystemPreference);
  
  const [anchorEl, setAnchorEl] = useState<null | HTMLElement>(null);
  const open = Boolean(anchorEl);
  
  const handleClick = (event: React.MouseEvent<HTMLElement>) => {
    setAnchorEl(event.currentTarget);
  };
  
  const handleClose = () => {
    setAnchorEl(null);
  };
  
  const handleThemeToggle = () => {
    dispatch(toggleThemeMode());
    handleClose();
  };
  
  const handleSystemPreferenceToggle = (event: React.ChangeEvent<HTMLInputElement>) => {
    dispatch(setUseSystemPreference(event.target.checked));
  };
  
  return (
    <>
      <Tooltip title="Theme settings">
        <IconButton
          onClick={handleClick}
          color="inherit"
          aria-label="toggle theme"
          aria-controls={open ? 'theme-menu' : undefined}
          aria-haspopup="true"
          aria-expanded={open ? 'true' : undefined}
        >
          {themeMode === 'dark' ? <Brightness7Icon /> : <Brightness4Icon />}
        </IconButton>
      </Tooltip>
      
      <Menu
        id="theme-menu"
        anchorEl={anchorEl}
        open={open}
        onClose={handleClose}
        MenuListProps={{
          'aria-labelledby': 'theme-button',
        }}
      >
        <MenuItem onClick={handleThemeToggle}>
          {themeMode === 'light' ? 'Switch to Dark Mode' : 'Switch to Light Mode'}
        </MenuItem>
        
        <MenuItem>
          <Typography variant="body2" sx={{ mr: 1 }}>
            Use system preference
          </Typography>
          <Switch
            size="small"
            checked={useSystemPreference}
            onChange={handleSystemPreferenceToggle}
            inputProps={{ 'aria-label': 'use system theme preference' }}
          />
        </MenuItem>
      </Menu>
    </>
  );
};

export default ThemeToggle;