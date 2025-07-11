import React, { useState, useEffect, useContext } from 'react';
import { AuthContext } from '../contexts/AuthContext';
import './HistoryPage.css';

const HistoryPage = () => {
    const { authToken } = useContext(AuthContext);
    const [sessions, setSessions] = useState([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState(null);
    const [searchTerm, setSearchTerm] = useState('');
    const [filterStatus, setFilterStatus] = useState('');
    const [sortBy, setSortBy] = useState('start_time');
    const [sortOrder, setSortOrder] = useState('desc');
    const [currentPage, setCurrentPage] = useState(1);
    const [totalPages, setTotalPages] = useState(1);
    const [editingSession, setEditingSession] = useState(null);
    const [newSessionName, setNewSessionName] = useState('');

    const SESSIONS_PER_PAGE = 10;

    // Fetch session history
    const fetchSessions = async (page = 1) => {
        setLoading(true);
        setError(null);

        try {
            const offset = (page - 1) * SESSIONS_PER_PAGE;
            const params = new URLSearchParams({
                limit: SESSIONS_PER_PAGE.toString(),
                offset: offset.toString()
            });

            if (filterStatus) {
                params.append('status', filterStatus);
            }

            const response = await fetch(`/api/sessions/history?${params}`, {
                headers: {
                    'Authorization': `Bearer ${authToken}`,
                    'Content-Type': 'application/json'
                }
            });

            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }

            const data = await response.json();
            
            if (data.success) {
                setSessions(data.data.sessions);
                setTotalPages(Math.ceil(data.data.count / SESSIONS_PER_PAGE));
            } else {
                throw new Error(data.message || 'Failed to fetch sessions');
            }
        } catch (err) {
            console.error('Error fetching sessions:', err);
            setError(err.message);
        } finally {
            setLoading(false);
        }
    };

    // Update session name
    const updateSessionName = async (sessionId, name) => {
        try {
            const response = await fetch(`/api/sessions/${sessionId}/name`, {
                method: 'POST',
                headers: {
                    'Authorization': `Bearer ${authToken}`,
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({ name })
            });

            const data = await response.json();
            
            if (data.success) {
                // Update local state
                setSessions(prev => prev.map(session => 
                    session.id === sessionId 
                        ? { ...session, name: data.data.name }
                        : session
                ));
                setEditingSession(null);
                setNewSessionName('');
            } else {
                throw new Error(data.message || 'Failed to update session name');
            }
        } catch (err) {
            console.error('Error updating session name:', err);
            setError(err.message);
        }
    };

    // Format duration in minutes to human readable
    const formatDuration = (minutes) => {
        if (!minutes || minutes < 0) return '0 min';
        
        const hours = Math.floor(minutes / 60);
        const mins = minutes % 60;
        
        if (hours > 0) {
            return `${hours}h ${mins}m`;
        }
        return `${mins}m`;
    };

    // Format temperature with unit
    const formatTemperature = (temp) => {
        if (temp === null || temp === undefined) return 'N/A';
        return `${temp.toFixed(1)}°F`;
    };

    // Format date/time
    const formatDateTime = (dateString) => {
        if (!dateString) return 'N/A';
        
        const date = new Date(dateString);
        return new Intl.DateTimeFormat('en-US', {
            month: 'short',
            day: 'numeric',
            year: 'numeric',
            hour: 'numeric',
            minute: '2-digit',
            hour12: true
        }).format(date);
    };

    // Get status badge class
    const getStatusBadgeClass = (status) => {
        switch (status) {
            case 'active':
                return 'status-badge status-active';
            case 'completed':
                return 'status-badge status-completed';
            case 'cancelled':
                return 'status-badge status-cancelled';
            default:
                return 'status-badge';
        }
    };

    // Filter and sort sessions
    const getFilteredAndSortedSessions = () => {
        let filtered = sessions.filter(session => {
            const matchesSearch = !searchTerm || 
                (session.name && session.name.toLowerCase().includes(searchTerm.toLowerCase())) ||
                (session.session_type && session.session_type.toLowerCase().includes(searchTerm.toLowerCase()));
            
            const matchesFilter = !filterStatus || session.status === filterStatus;
            
            return matchesSearch && matchesFilter;
        });

        // Sort sessions
        filtered.sort((a, b) => {
            let aValue = a[sortBy];
            let bValue = b[sortBy];

            // Handle null/undefined values
            if (aValue === null || aValue === undefined) aValue = '';
            if (bValue === null || bValue === undefined) bValue = '';

            // Handle date fields
            if (sortBy === 'start_time' || sortBy === 'end_time') {
                aValue = new Date(aValue);
                bValue = new Date(bValue);
            }

            // Handle numeric fields
            if (sortBy === 'duration_minutes' || sortBy === 'max_temperature') {
                aValue = parseFloat(aValue) || 0;
                bValue = parseFloat(bValue) || 0;
            }

            let comparison = 0;
            if (aValue < bValue) comparison = -1;
            if (aValue > bValue) comparison = 1;

            return sortOrder === 'desc' ? -comparison : comparison;
        });

        return filtered;
    };

    // Handle sort change
    const handleSort = (field) => {
        if (sortBy === field) {
            setSortOrder(sortOrder === 'asc' ? 'desc' : 'asc');
        } else {
            setSortBy(field);
            setSortOrder('desc');
        }
    };

    // Handle edit session name
    const handleEditSessionName = (session) => {
        setEditingSession(session.id);
        setNewSessionName(session.name || '');
    };

    // Handle save session name
    const handleSaveSessionName = (sessionId) => {
        if (newSessionName.trim()) {
            updateSessionName(sessionId, newSessionName.trim());
        } else {
            setEditingSession(null);
            setNewSessionName('');
        }
    };

    // Handle cancel edit
    const handleCancelEdit = () => {
        setEditingSession(null);
        setNewSessionName('');
    };

    // Load sessions on component mount and when filters change
    useEffect(() => {
        fetchSessions(currentPage);
    }, [currentPage, filterStatus, authToken]);

    const filteredSessions = getFilteredAndSortedSessions();

    if (loading && sessions.length === 0) {
        return (
            <div className="history-page">
                <div className="loading-spinner">
                    <div className="spinner"></div>
                    <p>Loading session history...</p>
                </div>
            </div>
        );
    }

    return (
        <div className="history-page">
            <div className="history-header">
                <h1>Session History</h1>
                <p>Track and review your grilling sessions</p>
            </div>

            {error && (
                <div className="error-message">
                    <i className="error-icon">⚠️</i>
                    <span>{error}</span>
                    <button onClick={() => fetchSessions(currentPage)} className="retry-button">
                        Retry
                    </button>
                </div>
            )}

            <div className="history-controls">
                <div className="search-filter-section">
                    <div className="search-box">
                        <input
                            type="text"
                            placeholder="Search sessions by name or type..."
                            value={searchTerm}
                            onChange={(e) => setSearchTerm(e.target.value)}
                            className="search-input"
                        />
                    </div>

                    <div className="filter-section">
                        <select
                            value={filterStatus}
                            onChange={(e) => setFilterStatus(e.target.value)}
                            className="status-filter"
                        >
                            <option value="">All Sessions</option>
                            <option value="completed">Completed</option>
                            <option value="active">Active</option>
                            <option value="cancelled">Cancelled</option>
                        </select>
                    </div>
                </div>

                <div className="results-info">
                    {filteredSessions.length} session{filteredSessions.length !== 1 ? 's' : ''} found
                </div>
            </div>

            {filteredSessions.length === 0 ? (
                <div className="empty-state">
                    <div className="empty-state-icon">🔥</div>
                    <h3>No grilling sessions found</h3>
                    <p>
                        {sessions.length === 0 
                            ? "Start grilling to see your session history here!"
                            : "Try adjusting your search or filter criteria."
                        }
                    </p>
                </div>
            ) : (
                <>
                    <div className="sessions-table-container">
                        <table className="sessions-table">
                            <thead>
                                <tr>
                                    <th 
                                        onClick={() => handleSort('name')} 
                                        className={sortBy === 'name' ? 'sortable active' : 'sortable'}
                                    >
                                        Session Name
                                        {sortBy === 'name' && (
                                            <span className="sort-indicator">
                                                {sortOrder === 'asc' ? '↑' : '↓'}
                                            </span>
                                        )}
                                    </th>
                                    <th 
                                        onClick={() => handleSort('start_time')} 
                                        className={sortBy === 'start_time' ? 'sortable active' : 'sortable'}
                                    >
                                        Start Time
                                        {sortBy === 'start_time' && (
                                            <span className="sort-indicator">
                                                {sortOrder === 'asc' ? '↑' : '↓'}
                                            </span>
                                        )}
                                    </th>
                                    <th 
                                        onClick={() => handleSort('duration_minutes')} 
                                        className={sortBy === 'duration_minutes' ? 'sortable active' : 'sortable'}
                                    >
                                        Duration
                                        {sortBy === 'duration_minutes' && (
                                            <span className="sort-indicator">
                                                {sortOrder === 'asc' ? '↑' : '↓'}
                                            </span>
                                        )}
                                    </th>
                                    <th 
                                        onClick={() => handleSort('max_temperature')} 
                                        className={sortBy === 'max_temperature' ? 'sortable active' : 'sortable'}
                                    >
                                        Max Temp
                                        {sortBy === 'max_temperature' && (
                                            <span className="sort-indicator">
                                                {sortOrder === 'asc' ? '↑' : '↓'}
                                            </span>
                                        )}
                                    </th>
                                    <th 
                                        onClick={() => handleSort('session_type')} 
                                        className={sortBy === 'session_type' ? 'sortable active' : 'sortable'}
                                    >
                                        Type
                                        {sortBy === 'session_type' && (
                                            <span className="sort-indicator">
                                                {sortOrder === 'asc' ? '↑' : '↓'}
                                            </span>
                                        )}
                                    </th>
                                    <th 
                                        onClick={() => handleSort('status')} 
                                        className={sortBy === 'status' ? 'sortable active' : 'sortable'}
                                    >
                                        Status
                                        {sortBy === 'status' && (
                                            <span className="sort-indicator">
                                                {sortOrder === 'asc' ? '↑' : '↓'}
                                            </span>
                                        )}
                                    </th>
                                    <th>Actions</th>
                                </tr>
                            </thead>
                            <tbody>
                                {filteredSessions.map((session) => (
                                    <tr key={session.id} className="session-row">
                                        <td className="session-name-cell">
                                            {editingSession === session.id ? (
                                                <div className="edit-name-container">
                                                    <input
                                                        type="text"
                                                        value={newSessionName}
                                                        onChange={(e) => setNewSessionName(e.target.value)}
                                                        className="edit-name-input"
                                                        onKeyPress={(e) => {
                                                            if (e.key === 'Enter') {
                                                                handleSaveSessionName(session.id);
                                                            } else if (e.key === 'Escape') {
                                                                handleCancelEdit();
                                                            }
                                                        }}
                                                        autoFocus
                                                    />
                                                    <div className="edit-actions">
                                                        <button 
                                                            onClick={() => handleSaveSessionName(session.id)}
                                                            className="save-button"
                                                            title="Save"
                                                        >
                                                            ✓
                                                        </button>
                                                        <button 
                                                            onClick={handleCancelEdit}
                                                            className="cancel-button"
                                                            title="Cancel"
                                                        >
                                                            ✕
                                                        </button>
                                                    </div>
                                                </div>
                                            ) : (
                                                <div className="session-name">
                                                    <span>{session.name || 'Unnamed Session'}</span>
                                                    <button 
                                                        onClick={() => handleEditSessionName(session)}
                                                        className="edit-name-button"
                                                        title="Edit name"
                                                    >
                                                        ✏️
                                                    </button>
                                                </div>
                                            )}
                                        </td>
                                        <td className="start-time-cell">
                                            {formatDateTime(session.start_time)}
                                        </td>
                                        <td className="duration-cell">
                                            {session.status === 'active' 
                                                ? formatDuration(session.current_duration)
                                                : formatDuration(session.duration_minutes)
                                            }
                                        </td>
                                        <td className="max-temp-cell">
                                            {formatTemperature(session.max_temperature)}
                                        </td>
                                        <td className="session-type-cell">
                                            <span className="session-type-badge">
                                                {session.session_type || 'cooking'}
                                            </span>
                                        </td>
                                        <td className="status-cell">
                                            <span className={getStatusBadgeClass(session.status)}>
                                                {session.status}
                                            </span>
                                        </td>
                                        <td className="actions-cell">
                                            <button 
                                                className="view-details-button"
                                                title="View details (coming soon)"
                                                disabled
                                            >
                                                View
                                            </button>
                                        </td>
                                    </tr>
                                ))}
                            </tbody>
                        </table>
                    </div>

                    {totalPages > 1 && (
                        <div className="pagination">
                            <button 
                                onClick={() => setCurrentPage(prev => Math.max(prev - 1, 1))}
                                disabled={currentPage === 1}
                                className="pagination-button"
                            >
                                Previous
                            </button>
                            
                            <span className="pagination-info">
                                Page {currentPage} of {totalPages}
                            </span>
                            
                            <button 
                                onClick={() => setCurrentPage(prev => Math.min(prev + 1, totalPages))}
                                disabled={currentPage === totalPages}
                                className="pagination-button"
                            >
                                Next
                            </button>
                        </div>
                    )}
                </>
            )}

            {loading && sessions.length > 0 && (
                <div className="loading-overlay">
                    <div className="spinner"></div>
                </div>
            )}
        </div>
    );
};

export default HistoryPage;