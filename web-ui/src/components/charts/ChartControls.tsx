import { useState } from 'react';
import {
  Box,
  ToggleButton,
  ToggleButtonGroup,
  IconButton,
  Tooltip,
  Menu,
  MenuItem,
  Switch,
  FormControlLabel,
  TextField,
  Button,
  Card,
  CardContent,
  Typography,
  Grid,
  Divider,
} from '@mui/material';
import SettingsIcon from '@mui/icons-material/Settings';
import RefreshIcon from '@mui/icons-material/Refresh';
import GridOnIcon from '@mui/icons-material/GridOn';
import GridOffIcon from '@mui/icons-material/GridOff';
import LegendToggleIcon from '@mui/icons-material/LegendToggle';
import CalendarTodayIcon from '@mui/icons-material/CalendarToday';
import { useAppDispatch, useAppSelector } from '@/hooks/reduxHooks';
import {
  setChartTimeRange,
  setCustomTimeRange,
  setRealtimeEnabled,
  setChartOptions,
  setManualTempRange,
  selectChartTimeRange,
  selectCustomTimeRange,
  selectRealtimeEnabled,
  selectChartOptions,
  selectTempRange,
} from '@/store/slices/temperatureSlice';
import { api } from '@/store/api';

interface ChartControlsProps {
  deviceId: string;
  probeId?: string;
  onRefresh?: () => void;
}

/**
 * Controls for temperature chart time range and display options
 */
const ChartControls = ({ deviceId, probeId, onRefresh }: ChartControlsProps) => {
  const dispatch = useAppDispatch();
  const timeRange = useAppSelector(selectChartTimeRange);
  const customRange = useAppSelector(selectCustomTimeRange);
  const realtimeEnabled = useAppSelector(selectRealtimeEnabled);
  const { showGridlines, showLegend } = useAppSelector(selectChartOptions);
  const { manual: manualTempRange, min: minTemp, max: maxTemp } = useAppSelector(selectTempRange);
  
  const [settingsAnchorEl, setSettingsAnchorEl] = useState<null | HTMLElement>(null);
  const [customDateAnchorEl, setCustomDateAnchorEl] = useState<null | HTMLElement>(null);
  const [tempMin, setTempMin] = useState<string>(minTemp?.toString() || '');
  const [tempMax, setTempMax] = useState<string>(maxTemp?.toString() || '');
  const [customStart, setCustomStart] = useState<string>(
    customRange.start ? new Date(customRange.start).toISOString().substring(0, 16) : ''
  );
  const [customEnd, setCustomEnd] = useState<string>(
    customRange.end ? new Date(customRange.end).toISOString().substring(0, 16) : ''
  );
  
  // Temperature history API call
  const { refetch } = api.useGetTemperatureHistoryQuery({
    deviceId,
    probeId,
    startTime: customRange.start || new Date(Date.now() - 3600000).toISOString(),
    endTime: customRange.end || new Date().toISOString(),
  });
  
  // Handle time range change
  const handleTimeRangeChange = (_event: React.MouseEvent<HTMLElement>, newRange: string) => {
    if (newRange) {
      dispatch(setChartTimeRange(newRange as any));
    }
  };
  
  // Handle settings menu
  const handleSettingsClick = (event: React.MouseEvent<HTMLElement>) => {
    setSettingsAnchorEl(event.currentTarget);
  };
  
  const handleSettingsClose = () => {
    setSettingsAnchorEl(null);
  };
  
  // Handle custom date picker
  const handleCustomDateClick = (event: React.MouseEvent<HTMLElement>) => {
    setCustomDateAnchorEl(event.currentTarget);
  };
  
  const handleCustomDateClose = () => {
    setCustomDateAnchorEl(null);
  };
  
  // Handle refresh button click
  const handleRefresh = () => {
    refetch();
    if (onRefresh) {
      onRefresh();
    }
  };
  
  // Toggle gridlines
  const handleGridlinesToggle = () => {
    dispatch(setChartOptions({ showGridlines: !showGridlines }));
  };
  
  // Toggle legend
  const handleLegendToggle = () => {
    dispatch(setChartOptions({ showLegend: !showLegend }));
  };
  
  // Toggle realtime updates
  const handleRealtimeToggle = (event: React.ChangeEvent<HTMLInputElement>) => {
    dispatch(setRealtimeEnabled(event.target.checked));
  };
  
  // Apply custom date range
  const handleApplyCustomDate = () => {
    if (customStart && customEnd) {
      dispatch(setCustomTimeRange({
        start: new Date(customStart).toISOString(),
        end: new Date(customEnd).toISOString(),
      }));
    }
    handleCustomDateClose();
  };
  
  // Toggle manual temperature range
  const handleManualTempRangeToggle = (event: React.ChangeEvent<HTMLInputElement>) => {
    dispatch(setManualTempRange({ 
      enabled: event.target.checked,
      min: tempMin ? parseFloat(tempMin) : null,
      max: tempMax ? parseFloat(tempMax) : null,
    }));
  };
  
  // Apply temperature range
  const handleApplyTempRange = () => {
    dispatch(setManualTempRange({
      enabled: manualTempRange,
      min: tempMin ? parseFloat(tempMin) : null,
      max: tempMax ? parseFloat(tempMax) : null,
    }));
  };
  
  return (
    <Card>
      <CardContent>
        <Box sx={{ display: 'flex', alignItems: 'center', flexWrap: 'wrap', gap: 2 }}>
          {/* Time Range Toggle */}
          <ToggleButtonGroup
            value={timeRange}
            exclusive
            onChange={handleTimeRangeChange}
            aria-label="chart time range"
            size="small"
          >
            <ToggleButton value="15m">15m</ToggleButton>
            <ToggleButton value="1h">1h</ToggleButton>
            <ToggleButton value="6h">6h</ToggleButton>
            <ToggleButton value="24h">24h</ToggleButton>
            <ToggleButton value="custom">Custom</ToggleButton>
          </ToggleButtonGroup>
          
          {/* Controls */}
          <Box sx={{ display: 'flex', ml: 'auto', gap: 1 }}>
            {/* Custom Date Range */}
            {timeRange === 'custom' && (
              <Tooltip title="Set custom date range">
                <IconButton onClick={handleCustomDateClick} size="small">
                  <CalendarTodayIcon />
                </IconButton>
              </Tooltip>
            )}
            
            {/* Toggle Gridlines */}
            <Tooltip title={showGridlines ? "Hide gridlines" : "Show gridlines"}>
              <IconButton onClick={handleGridlinesToggle} size="small">
                {showGridlines ? <GridOnIcon /> : <GridOffIcon />}
              </IconButton>
            </Tooltip>
            
            {/* Toggle Legend */}
            <Tooltip title={showLegend ? "Hide legend" : "Show legend"}>
              <IconButton onClick={handleLegendToggle} size="small">
                <LegendToggleIcon />
              </IconButton>
            </Tooltip>
            
            {/* Refresh */}
            <Tooltip title="Refresh data">
              <IconButton onClick={handleRefresh} size="small">
                <RefreshIcon />
              </IconButton>
            </Tooltip>
            
            {/* Settings */}
            <Tooltip title="Chart settings">
              <IconButton onClick={handleSettingsClick} size="small">
                <SettingsIcon />
              </IconButton>
            </Tooltip>
          </Box>
        </Box>
      </CardContent>
      
      {/* Settings Menu */}
      <Menu
        anchorEl={settingsAnchorEl}
        open={Boolean(settingsAnchorEl)}
        onClose={handleSettingsClose}
        anchorOrigin={{
          vertical: 'bottom',
          horizontal: 'right',
        }}
        transformOrigin={{
          vertical: 'top',
          horizontal: 'right',
        }}
      >
        <MenuItem>
          <FormControlLabel
            control={
              <Switch
                checked={realtimeEnabled}
                onChange={handleRealtimeToggle}
                color="primary"
              />
            }
            label="Real-time updates"
          />
        </MenuItem>
        
        <Divider />
        
        <MenuItem>
          <FormControlLabel
            control={
              <Switch
                checked={manualTempRange}
                onChange={handleManualTempRangeToggle}
                color="primary"
              />
            }
            label="Custom temperature range"
          />
        </MenuItem>
        
        {manualTempRange && (
          <Box sx={{ px: 2, py: 1 }}>
            <Grid container spacing={2}>
              <Grid item xs={6}>
                <TextField
                  label="Min"
                  type="number"
                  value={tempMin}
                  onChange={(e) => setTempMin(e.target.value)}
                  size="small"
                  fullWidth
                />
              </Grid>
              <Grid item xs={6}>
                <TextField
                  label="Max"
                  type="number"
                  value={tempMax}
                  onChange={(e) => setTempMax(e.target.value)}
                  size="small"
                  fullWidth
                />
              </Grid>
              <Grid item xs={12}>
                <Button 
                  variant="outlined" 
                  onClick={handleApplyTempRange}
                  size="small"
                  fullWidth
                >
                  Apply Range
                </Button>
              </Grid>
            </Grid>
          </Box>
        )}
      </Menu>
      
      {/* Custom Date Picker */}
      <Menu
        anchorEl={customDateAnchorEl}
        open={Boolean(customDateAnchorEl)}
        onClose={handleCustomDateClose}
        anchorOrigin={{
          vertical: 'bottom',
          horizontal: 'right',
        }}
        transformOrigin={{
          vertical: 'top',
          horizontal: 'right',
        }}
      >
        <Box sx={{ p: 2, width: 300 }}>
          <Typography variant="subtitle1" sx={{ mb: 2 }}>
            Custom Date Range
          </Typography>
          
          <Grid container spacing={2}>
            <Grid item xs={12}>
              <TextField
                label="Start"
                type="datetime-local"
                value={customStart}
                onChange={(e) => setCustomStart(e.target.value)}
                fullWidth
                InputLabelProps={{ shrink: true }}
              />
            </Grid>
            <Grid item xs={12}>
              <TextField
                label="End"
                type="datetime-local"
                value={customEnd}
                onChange={(e) => setCustomEnd(e.target.value)}
                fullWidth
                InputLabelProps={{ shrink: true }}
              />
            </Grid>
            <Grid item xs={12}>
              <Button 
                variant="contained" 
                onClick={handleApplyCustomDate}
                fullWidth
                disabled={!customStart || !customEnd}
              >
                Apply
              </Button>
            </Grid>
          </Grid>
        </Box>
      </Menu>
    </Card>
  );
};

export default ChartControls;