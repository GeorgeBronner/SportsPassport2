import React, { useState, useEffect } from 'react';
import { adminApi } from '../api/admin';
import type { User } from '../types/api';
import Layout from '../components/layout/Layout';
import Card from '../components/common/Card';
import Button from '../components/common/Button';
import Loading from '../components/common/Loading';
import Alert from '../components/common/Alert';

const Admin: React.FC = () => {
  const [users, setUsers] = useState<User[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');
  const [refreshSeason, setRefreshSeason] = useState(new Date().getFullYear());
  const [refreshing, setRefreshing] = useState(false);

  useEffect(() => {
    loadUsers();
  }, []);

  const loadUsers = async () => {
    setLoading(true);
    try {
      const data = await adminApi.getUsers();
      setUsers(data.sort((a, b) => a.email.localeCompare(b.email)));
    } catch (err) {
      setError('Failed to load users');
    } finally {
      setLoading(false);
    }
  };

  const handlePromote = async (userId: number) => {
    try {
      const updatedUser = await adminApi.promoteUser(userId);
      setUsers(users.map((u) => (u.id === userId ? updatedUser : u)));
      setSuccess('User promoted to admin');
      setTimeout(() => setSuccess(''), 3000);
    } catch (err) {
      setError('Failed to promote user');
    }
  };

  const handleDemote = async (userId: number) => {
    try {
      const updatedUser = await adminApi.demoteUser(userId);
      setUsers(users.map((u) => (u.id === userId ? updatedUser : u)));
      setSuccess('User demoted from admin');
      setTimeout(() => setSuccess(''), 3000);
    } catch (err) {
      setError('Failed to demote user');
    }
  };

  const handleRefreshData = async () => {
    if (!confirm(`This will import all games for the ${refreshSeason} season. This may take a while. Continue?`)) {
      return;
    }

    setRefreshing(true);
    setError('');
    try {
      await adminApi.refreshData(refreshSeason);
      setSuccess(`Successfully imported ${refreshSeason} season data`);
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to refresh data');
    } finally {
      setRefreshing(false);
    }
  };

  if (loading) {
    return <Loading message="Loading admin panel..." />;
  }

  return (
    <Layout>
      <div>
        <h1 className="text-3xl font-bold text-gray-900 mb-6">Admin Dashboard</h1>

        {error && <Alert type="error" message={error} onClose={() => setError('')} />}
        {success && <Alert type="success" message={success} onClose={() => setSuccess('')} />}

        <div className="grid grid-cols-1 md:grid-cols-2 gap-6 mb-6">
          <Card>
            <h2 className="text-xl font-semibold mb-4">Data Management</h2>
            <p className="text-sm text-gray-600 mb-4">
              Import game data from CollegeFootballData.com API
            </p>

            <div className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Season Year
                </label>
                <input
                  type="number"
                  value={refreshSeason}
                  onChange={(e) => setRefreshSeason(Number(e.target.value))}
                  min="1990"
                  max={new Date().getFullYear() + 1}
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
                />
              </div>

              <Button
                onClick={handleRefreshData}
                disabled={refreshing}
                className="w-full"
              >
                {refreshing ? 'Importing Data...' : 'Import Season Data'}
              </Button>

              <p className="text-xs text-gray-500">
                Note: This will import all FBS games for the selected season. Existing games will be skipped.
              </p>
            </div>
          </Card>

          <Card>
            <h2 className="text-xl font-semibold mb-4">System Statistics</h2>
            <div className="space-y-3">
              <div className="flex justify-between items-center p-3 bg-gray-50 rounded">
                <span className="text-gray-700">Total Users</span>
                <span className="font-semibold text-blue-600">{users.length}</span>
              </div>
              <div className="flex justify-between items-center p-3 bg-gray-50 rounded">
                <span className="text-gray-700">Admin Users</span>
                <span className="font-semibold text-blue-600">
                  {users.filter((u) => u.is_admin).length}
                </span>
              </div>
              <div className="flex justify-between items-center p-3 bg-gray-50 rounded">
                <span className="text-gray-700">Regular Users</span>
                <span className="font-semibold text-blue-600">
                  {users.filter((u) => !u.is_admin).length}
                </span>
              </div>
            </div>
          </Card>
        </div>

        <Card>
          <h2 className="text-xl font-semibold mb-4">User Management</h2>
          <div className="overflow-x-auto">
            <table className="min-w-full divide-y divide-gray-200">
              <thead className="bg-gray-50">
                <tr>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Email
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Name
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Role
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Actions
                  </th>
                </tr>
              </thead>
              <tbody className="bg-white divide-y divide-gray-200">
                {users.map((user) => (
                  <tr key={user.id}>
                    <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">
                      {user.email}
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">
                      {user.full_name}
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap">
                      {user.is_admin ? (
                        <span className="px-2 inline-flex text-xs leading-5 font-semibold rounded-full bg-green-100 text-green-800">
                          Admin
                        </span>
                      ) : (
                        <span className="px-2 inline-flex text-xs leading-5 font-semibold rounded-full bg-gray-100 text-gray-800">
                          User
                        </span>
                      )}
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm">
                      {user.is_admin ? (
                        <Button
                          size="sm"
                          variant="secondary"
                          onClick={() => handleDemote(user.id)}
                        >
                          Demote
                        </Button>
                      ) : (
                        <Button
                          size="sm"
                          onClick={() => handlePromote(user.id)}
                        >
                          Promote to Admin
                        </Button>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Card>
      </div>
    </Layout>
  );
};

export default Admin;
