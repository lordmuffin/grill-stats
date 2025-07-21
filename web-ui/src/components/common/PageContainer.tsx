import { ReactNode } from 'react';
import { Box, Container, Paper, Typography, Breadcrumbs, Link } from '@mui/material';
import { Link as RouterLink } from 'react-router-dom';
import NavigateNextIcon from '@mui/icons-material/NavigateNext';

interface BreadcrumbItem {
  label: string;
  link?: string;
}

interface PageContainerProps {
  title: string;
  description?: string;
  breadcrumbs?: BreadcrumbItem[];
  children: ReactNode;
  maxWidth?: 'xs' | 'sm' | 'md' | 'lg' | 'xl' | false;
  paper?: boolean;
  sx?: object;
  disableGutters?: boolean;
}

/**
 * A container component for page content with title, description, and breadcrumbs
 */
const PageContainer = ({
  title,
  description,
  breadcrumbs,
  children,
  maxWidth = 'lg',
  paper = true,
  sx = {},
  disableGutters = false,
}: PageContainerProps) => {
  return (
    <Container maxWidth={maxWidth} disableGutters={disableGutters}>
      {breadcrumbs && breadcrumbs.length > 0 && (
        <Box sx={{ mt: 2, mb: 3 }}>
          <Breadcrumbs
            separator={<NavigateNextIcon fontSize="small" />}
            aria-label="breadcrumb"
          >
            {breadcrumbs.map((item, index) => {
              const isLast = index === breadcrumbs.length - 1;
              
              return isLast || !item.link ? (
                <Typography key={item.label} color="text.primary">
                  {item.label}
                </Typography>
              ) : (
                <Link
                  key={item.label}
                  component={RouterLink}
                  to={item.link}
                  underline="hover"
                  color="inherit"
                >
                  {item.label}
                </Link>
              );
            })}
          </Breadcrumbs>
        </Box>
      )}
      
      <Box sx={{ mb: 4 }}>
        <Typography variant="h4" component="h1" gutterBottom>
          {title}
        </Typography>
        
        {description && (
          <Typography variant="body1" color="text.secondary">
            {description}
          </Typography>
        )}
      </Box>
      
      {paper ? (
        <Paper
          elevation={2}
          sx={{
            p: 3,
            mb: 4,
            borderRadius: 2,
            ...sx,
          }}
        >
          {children}
        </Paper>
      ) : (
        <Box sx={{ mb: 4, ...sx }}>{children}</Box>
      )}
    </Container>
  );
};

export default PageContainer;