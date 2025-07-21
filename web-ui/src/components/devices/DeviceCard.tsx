import { useState } from 'react';
import {
  Card,
  CardContent,
  CardActions,
  Typography,
  Chip,
  Box,
  IconButton,
  Menu,
  MenuItem,
  ListItemIcon,
  ListItemText,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogContentText,
  DialogActions,
  Button,
  TextField,
  Tooltip,
  Badge,
} from '@mui/material';
import EditIcon from '@mui/icons-material/Edit';
import DeleteIcon from '@mui/icons-material/Delete';
import MoreVertIcon from '@mui/icons-material/MoreVert';
import SettingsIcon from '@mui/icons-material/Settings';
import RefreshIcon from '@mui/icons-material/Refresh';
import BatteryFullIcon from '@mui/icons-material/BatteryFull';
import BatteryAlertIcon from '@mui/icons-material/BatteryAlert';
import SignalCellularAltIcon from '@mui/icons-material/SignalCellularAlt';
import SignalCellularOffIcon from '@mui/icons-material/SignalCellularOff';
import { formatDistanceToNow } from 'date-fns';
import { api } from '@/store/api';
import useAlerts from '@/hooks/useAlerts';
import type { Device } from '@/types';

interface DeviceCardProps {
  device: Device;
  onRefresh?: () => void;
}

/**
 * Card component for displaying device information
 */
const DeviceCard = ({ device, onRefresh }: DeviceCardProps) => {
  const { showSuccess, showError } = useAlerts();
  
  // State
  const [menuAnchorEl, setMenuAnchorEl] = useState<null | HTMLElement>(null);
  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false);
  const [editDialogOpen, setEditDialogOpen] = useState(false);
  const [nickname, setNickname] = useState(device.nickname || '');
  
  // API hooks
  const [updateDeviceNickname, { isLoading: isUpdating }] = api.useUpdateDeviceNicknameMutation();
  const [removeDevice, { isLoading: isRemoving }] = api.useRemoveDeviceMutation();
  
  // Menu handlers
  const handleMenuOpen = (event: React.MouseEvent<HTMLElement>) => {
    setMenuAnchorEl(event.currentTarget);
  };
  
  const handleMenuClose = () => {
    setMenuAnchorEl(null);
  };
  
  // Edit dialog handlers
  const handleEditOpen = () => {
    setNickname(device.nickname || '');
    setEditDialogOpen(true);
    handleMenuClose();
  };
  
  const handleEditClose = () => {
    setEditDialogOpen(false);
  };
  
  const handleNicknameUpdate = async () => {
    try {
      await updateDeviceNickname({
        deviceId: device.id,
        nickname,
      }).unwrap();
      
      showSuccess('Device nickname updated successfully');
      setEditDialogOpen(false);
    } catch (error) {
      showError(`Failed to update nickname: ${error instanceof Error ? error.message : 'Unknown error'}`);
    }
  };
  
  // Delete dialog handlers
  const handleDeleteOpen = () => {
    setDeleteDialogOpen(true);
    handleMenuClose();
  };
  
  const handleDeleteClose = () => {
    setDeleteDialogOpen(false);
  };
  
  const handleDeviceRemove = async () => {
    try {
      await removeDevice(device.id).unwrap();
      
      showSuccess(`Device ${device.nickname || device.deviceId} successfully removed`);
      setDeleteDialogOpen(false);
    } catch (error) {
      showError(`Failed to remove device: ${error instanceof Error ? error.message : 'Unknown error'}`);
    }
  };
  
  // Helper functions
  const getStatusColor = (status: string) => {
    switch (status) {
      case 'online':
        return 'success';
      case 'offline':
        return 'error';
      default:
        return 'default';
    }
  };
  
  const getBatteryIcon = () => {
    if (!device.batteryLevel || device.batteryLevel < 20) {
      return (
        <Tooltip title="Low Battery">
          <Badge color="error" variant="dot">
            <BatteryAlertIcon color="error" />
          </Badge>
        </Tooltip>
      );
    }
    return (
      <Tooltip title={`Battery: ${device.batteryLevel}%`}>
        <BatteryFullIcon color={device.batteryLevel < 40 ? 'warning' : 'success'} />
      </Tooltip>
    );
  };
  
  const getSignalIcon = () => {
    if (!device.signalStrength || device.signalStrength < 20) {
      return (
        <Tooltip title="Poor Signal">
          <SignalCellularOffIcon color="error" />
        </Tooltip>
      );
    }
    return (
      <Tooltip title={`Signal: ${device.signalStrength}%`}>
        <SignalCellularAltIcon color={device.signalStrength < 40 ? 'warning' : 'success'} />
      </Tooltip>
    );
  };
  
  return (
    <>
      <Card sx={{ height: '100%', display: 'flex', flexDirection: 'column' }}>
        <CardContent sx={{ flexGrow: 1 }}>
          <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
            <Typography variant="h6" component="div" noWrap>
              {device.nickname || device.deviceId}
            </Typography>
            
            <IconButton size="small" onClick={handleMenuOpen}>
              <MoreVertIcon />
            </IconButton>
          </Box>
          
          <Typography variant="body2" color="text.secondary" gutterBottom noWrap>
            ID: {device.deviceId}
          </Typography>
          
          <Box sx={{ mt: 2, display: 'flex', alignItems: 'center', gap: 1 }}>
            <Chip
              label={device.status}
              color={getStatusColor(device.status) as 'success' | 'error' | 'default'}
              size="small"
            />
            
            <Box sx={{ ml: 'auto', display: 'flex', gap: 1 }}>
              {getBatteryIcon()}
              {getSignalIcon()}
            </Box>
          </Box>
          
          {device.probes && device.probes.length > 0 && (
            <Box sx={{ mt: 2 }}>
              <Typography variant="body2" color="text.secondary" gutterBottom>
                Probes: {device.probes.length}
              </Typography>
              <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 0.5 }}>
                {device.probes.map((probe) => (
                  <Chip
                    key={probe.id}
                    label={probe.name || `Probe ${probe.probeId}`}
                    size="small"
                    variant="outlined"
                  />
                ))}
              </Box>
            </Box>
          )}
        </CardContent>
        
        <CardActions sx={{ 
          borderTop: '1px solid', 
          borderColor: 'divider',
          justifyContent: 'space-between',
          px: 2,
          py: 1,
        }}>
          <Typography variant="caption" color="text.secondary">
            {device.lastConnection ? (
              `Last seen ${formatDistanceToNow(new Date(device.lastConnection), { addSuffix: true })}`
            ) : (
              'Never connected'
            )}
          </Typography>
          
          <Tooltip title="Refresh">
            <IconButton size="small" onClick={onRefresh}>
              <RefreshIcon fontSize="small" />
            </IconButton>
          </Tooltip>
        </CardActions>
      </Card>
      
      {/* Device Menu */}
      <Menu
        anchorEl={menuAnchorEl}
        open={Boolean(menuAnchorEl)}
        onClose={handleMenuClose}
      >
        <MenuItem onClick={handleEditOpen}>
          <ListItemIcon>
            <EditIcon fontSize="small" />
          </ListItemIcon>
          <ListItemText>Edit Nickname</ListItemText>
        </MenuItem>
        
        <MenuItem onClick={handleMenuClose}>
          <ListItemIcon>
            <SettingsIcon fontSize="small" />
          </ListItemIcon>
          <ListItemText>Device Settings</ListItemText>
        </MenuItem>
        
        <MenuItem onClick={handleDeleteOpen} sx={{ color: 'error.main' }}>
          <ListItemIcon>
            <DeleteIcon fontSize="small" color="error" />
          </ListItemIcon>
          <ListItemText>Remove Device</ListItemText>
        </MenuItem>
      </Menu>
      
      {/* Edit Nickname Dialog */}
      <Dialog open={editDialogOpen} onClose={handleEditClose}>
        <DialogTitle>Edit Device Nickname</DialogTitle>
        <DialogContent>
          <DialogContentText>
            Enter a new nickname for this device.
          </DialogContentText>
          <TextField
            autoFocus
            margin="dense"
            label="Nickname"
            fullWidth
            value={nickname}
            onChange={(e) => setNickname(e.target.value)}
            variant="outlined"
          />
        </DialogContent>
        <DialogActions>
          <Button onClick={handleEditClose}>Cancel</Button>
          <Button 
            onClick={handleNicknameUpdate} 
            variant="contained"
            disabled={isUpdating}
          >
            Save
          </Button>
        </DialogActions>
      </Dialog>
      
      {/* Delete Confirmation Dialog */}
      <Dialog open={deleteDialogOpen} onClose={handleDeleteClose}>
        <DialogTitle>Remove Device</DialogTitle>
        <DialogContent>
          <DialogContentText>
            Are you sure you want to remove "{device.nickname || device.deviceId}"? 
            This device will no longer appear in your dashboard.
          </DialogContentText>
        </DialogContent>
        <DialogActions>
          <Button onClick={handleDeleteClose}>Cancel</Button>
          <Button 
            onClick={handleDeviceRemove} 
            color="error"
            disabled={isRemoving}
          >
            Remove
          </Button>
        </DialogActions>
      </Dialog>
    </>
  );
};

export default DeviceCard;