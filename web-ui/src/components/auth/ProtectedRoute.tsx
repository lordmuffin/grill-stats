import { Navigate, Outlet } from 'react-router-dom';
import { useAppSelector } from '@/hooks/reduxHooks';
import { selectIsAuthenticated, selectAuthChecked } from '@/store/slices/authSlice';
import LoadingScreen from '@/components/common/LoadingScreen';
import MainLayout from '@/components/layout/MainLayout';

/**
 * A wrapper component that protects routes by checking authentication.
 * Redirects to login if user is not authenticated.
 */
const ProtectedRoute = () => {
  const isAuthenticated = useAppSelector(selectIsAuthenticated);
  const authChecked = useAppSelector(selectAuthChecked);

  if (!authChecked) {
    // Still checking authentication status
    return <LoadingScreen />;
  }

  if (!isAuthenticated) {
    // Redirect to login page if not authenticated
    return <Navigate to="/login" replace />;
  }

  // Render child routes within the main layout
  return (
    <MainLayout>
      <Outlet />
    </MainLayout>
  );
};

export default ProtectedRoute;