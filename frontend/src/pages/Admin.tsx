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
        <h1 className="text-4xl font-bold text-gray-900 mb-8">Admin Dashboard</h1>

        {error && <Alert type="error" message={error} onClose={() => setError('')} />}
        {success && <Alert type="success" message={success} onClose={() => setSuccess('')} />}

        <div className="grid grid-cols-1 md:grid-cols-2 gap-8 mb-8">
          <Card className="bg-gradient-to-br from-primary-50 to-white border-primary-100">
            <h2 className="text-2xl font-bold text-primary-700 mb-4">Data Management</h2>
            <p className="text-sm text-gray-700 mb-6 font-medium">
              Import game data from CollegeFootballData.com API
            </p>

            <div className="space-y-4">
              <div>
                <label className="block text-sm font-bold text-gray-700 mb-2 uppercase tracking-wide">
                  Season Year
                </label>
                <input
                  type="number"
                  value={refreshSeason}
                  onChange={(e) => setRefreshSeason(Number(e.target.value))}
                  min="1990"
                  max={new Date().getFullYear() + 1}
                  className="w-full px-4 py-3 border border-gray-300 rounded-xl focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-transparent"
                />
              </div>

              <Button
                onClick={handleRefreshData}
                disabled={refreshing}
                className="w-full"
              >
                {refreshing ? 'Importing Data...' : 'Import Season Data'}
              </Button>

              <p className="text-xs text-gray-600 bg-primary-50 p-3 rounded-lg">
                Note: This will import all FBS games for the selected season. Existing games will be skipped.
              </p>
            </div>
          </Card>

          <Card className="bg-gradient-to-br from-sage-50 to-white border-sage-100">
            <h2 className="text-2xl font-bold text-sage-700 mb-6">System Statistics</h2>
            <div className="space-y-3">
              <div className="flex justify-between items-center p-4 bg-white rounded-xl shadow-sm">
                <span className="text-gray-800 font-medium">Total Users</span>
                <span className="font-bold text-sage-600 text-lg">{users.length}</span>
              </div>
              <div className="flex justify-between items-center p-4 bg-white rounded-xl shadow-sm">
                <span className="text-gray-800 font-medium">Admin Users</span>
                <span className="font-bold text-sage-600 text-lg">
                  {users.filter((u) => u.is_admin).length}
                </span>
              </div>
              <div className="flex justify-between items-center p-4 bg-white rounded-xl shadow-sm">
                <span className="text-gray-800 font-medium">Regular Users</span>
                <span className="font-bold text-sage-600 text-lg">
                  {users.filter((u) => !u.is_admin).length}
                </span>
              </div>
            </div>
          </Card>
        </div>

        <Card className="bg-gradient-to-br from-accent-50 to-white border-accent-100">
          <h2 className="text-2xl font-bold text-accent-700 mb-6">User Management</h2>
          <div className="overflow-x-auto">
            <table className="min-w-full divide-y divide-gray-200">
              <thead className="bg-gradient-to-r from-accent-100 to-accent-50">
                <tr>
                  <th className="px-6 py-4 text-left text-xs font-bold text-gray-700 uppercase tracking-wider">
                    Email
                  </th>
                  <th className="px-6 py-4 text-left text-xs font-bold text-gray-700 uppercase tracking-wider">
                    Name
                  </th>
                  <th className="px-6 py-4 text-left text-xs font-bold text-gray-700 uppercase tracking-wider">
                    Role
                  </th>
                  <th className="px-6 py-4 text-left text-xs font-bold text-gray-700 uppercase tracking-wider">
                    Actions
                  </th>
                </tr>
              </thead>
              <tbody className="bg-white divide-y divide-gray-100">
                {users.map((user) => (
                  <tr key={user.id} className="hover:bg-gray-50 transition-colors">
                    <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900 font-medium">
                      {user.email}
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">
                      {user.full_name}
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap">
                      {user.is_admin ? (
                        <span className="px-3 py-1 inline-flex text-xs leading-5 font-bold rounded-full bg-sage-100 text-sage-800">
                          Admin
                        </span>
                      ) : (
                        <span className="px-3 py-1 inline-flex text-xs leading-5 font-bold rounded-full bg-gray-100 text-gray-700">
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
