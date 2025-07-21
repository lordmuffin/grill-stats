import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { 
  Box, 
  IconButton, 
  Menu, 
  MenuItem, 
  ListItemText, 
  ListItemIcon,
  Tooltip 
} from '@mui/material';
import LanguageIcon from '@mui/icons-material/Language';
import CheckIcon from '@mui/icons-material/Check';
import { AVAILABLE_LANGUAGES, changeLanguage } from '@/i18n';

/**
 * Component for changing the application language
 */
const LanguageSelector = () => {
  const { i18n } = useTranslation();
  const [anchorEl, setAnchorEl] = useState<null | HTMLElement>(null);
  const open = Boolean(anchorEl);
  
  const handleClick = (event: React.MouseEvent<HTMLElement>) => {
    setAnchorEl(event.currentTarget);
  };
  
  const handleClose = () => {
    setAnchorEl(null);
  };
  
  const handleLanguageChange = (language: string) => {
    changeLanguage(language);
    handleClose();
  };
  
  const currentLanguage = i18n.language?.split('-')[0] || 'en';
  
  return (
    <Box>
      <Tooltip title="Change language">
        <IconButton
          onClick={handleClick}
          size="small"
          aria-controls={open ? 'language-menu' : undefined}
          aria-haspopup="true"
          aria-expanded={open ? 'true' : undefined}
          color="inherit"
        >
          <LanguageIcon />
        </IconButton>
      </Tooltip>
      
      <Menu
        id="language-menu"
        anchorEl={anchorEl}
        open={open}
        onClose={handleClose}
        MenuListProps={{
          'aria-labelledby': 'language-button',
        }}
      >
        {Object.entries(AVAILABLE_LANGUAGES).map(([code, name]) => (
          <MenuItem 
            key={code} 
            onClick={() => handleLanguageChange(code)}
            selected={currentLanguage === code}
          >
            <ListItemIcon>
              {currentLanguage === code && <CheckIcon fontSize="small" />}
            </ListItemIcon>
            <ListItemText>{name}</ListItemText>
          </MenuItem>
        ))}
      </Menu>
    </Box>
  );
};

export default LanguageSelector;