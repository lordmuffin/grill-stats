import { createSlice, PayloadAction } from '@reduxjs/toolkit';
import type { RootState } from '../index';
import type { Device } from '@/types';

interface DeviceState {
  selectedDevice: string | null;
  selectedProbe: string | null;
  deviceDiscoveryOpen: boolean;
}

const initialState: DeviceState = {
  selectedDevice: null,
  selectedProbe: null,
  deviceDiscoveryOpen: false,
};

const deviceSlice = createSlice({
  name: 'devices',
  initialState,
  reducers: {
    setSelectedDevice: (state, action: PayloadAction<string | null>) => {
      state.selectedDevice = action.payload;
      // Reset selected probe when changing devices
      state.selectedProbe = null;
    },
    setSelectedProbe: (state, action: PayloadAction<string | null>) => {
      state.selectedProbe = action.payload;
    },
    openDeviceDiscovery: (state) => {
      state.deviceDiscoveryOpen = true;
    },
    closeDeviceDiscovery: (state) => {
      state.deviceDiscoveryOpen = false;
    },
  },
});

// Export actions
export const {
  setSelectedDevice,
  setSelectedProbe,
  openDeviceDiscovery,
  closeDeviceDiscovery,
} = deviceSlice.actions;

// Export selectors
export const selectSelectedDevice = (state: RootState) => state.devices.selectedDevice;
export const selectSelectedProbe = (state: RootState) => state.devices.selectedProbe;
export const selectDeviceDiscoveryOpen = (state: RootState) => state.devices.deviceDiscoveryOpen;

// Create a memoized selector to find the selected device object
export const selectSelectedDeviceObject = (state: RootState, devices: Device[]) => {
  if (!state.devices.selectedDevice) return null;
  return devices.find(device => device.id === state.devices.selectedDevice) || null;
};

export default deviceSlice.reducer;