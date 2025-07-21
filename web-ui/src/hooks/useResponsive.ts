import { useEffect } from 'react';
import { useAppDispatch, useAppSelector } from './reduxHooks';
import { setMobileMode } from '@/store/slices/uiSlice';
import { selectMobileMode } from '@/store/slices/uiSlice';

/**
 * Hook to handle responsive UI adjustments
 * 
 * @param mobileBreakpoint Breakpoint width for mobile mode (default: 768)
 * @returns Current mobile mode state
 */
export const useResponsive = (mobileBreakpoint = 768) => {
  const dispatch = useAppDispatch();
  const isMobile = useAppSelector(selectMobileMode);
  
  useEffect(() => {
    // Set initial state
    const checkMobileMode = () => {
      const isMobileView = window.innerWidth < mobileBreakpoint;
      dispatch(setMobileMode(isMobileView));
    };
    
    // Check on initial render
    checkMobileMode();
    
    // Add resize listener
    window.addEventListener('resize', checkMobileMode);
    
    // Clean up event listener
    return () => {
      window.removeEventListener('resize', checkMobileMode);
    };
  }, [dispatch, mobileBreakpoint]);
  
  return isMobile;
};

export default useResponsive;