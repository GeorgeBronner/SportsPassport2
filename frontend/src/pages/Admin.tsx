import React, { useState, useEffect } from 'react';
import { adminApi } from '../api/admin';
import { leaguesApi } from '../api/leagues';
import type { User, League, AdminStatusRow } from '../types/api';
import Layout from '../components/layout/Layout';
import Card from '../components/common/Card';
import Button from '../components/common/Button';
import Loading from '../components/common/Loading';
import Alert from '../components/common/Alert';

const currentYear = new Date().getFullYear();

const Admin: React.FC = () => {
  const [users, setUsers] = useState<User[]>([]);
  const [leagues, setLeagues] = useState<League[]>([]);
  const [status, setStatus] = useState<AdminStatusRow[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');
  const [selectedLeague, setSelectedLeague] = useState('');
  const [startSeason, setStartSeason] = useState(currentYear - 1);
  const [endSeason, setEndSeason] = useState(currentYear);
  const [syncDays, setSyncDays] = useState(7);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    loadAll();
  }, []);

  const loadAll = async () => {
    setLoading(true);
    try {
      const [usersData, leaguesData, statusData] = await Promise.all([
        adminApi.getUsers(),
        leaguesApi.getLeagues(),
        adminApi.getStatus(),
      ]);
      setUsers(usersData.sort((a, b) => a.email.localeCompare(b.email)));
      setLeagues(leaguesData);
      setStatus(statusData);
      if (!selectedLeague && leaguesData.length) {
        setSelectedLeague(leaguesData[0].code);
      }
    } catch (err) {
      setError('Failed to load admin data');
    } finally {
      setLoading(false);
    }
  };

  const refreshStatus = async () => {
    try {
      setStatus(await adminApi.getStatus());
    } catch (err) {
      setError('Failed to refresh status');
    }
  };

  const runImport = async (action: () => Promise<{ teams_imported: number; games_imported: number; games_updated: number; errors: string[] }>, label: string) => {
    setBusy(true);
    setError('');
    try {
      const result = await action();
      const parts = [`${result.teams_imported} teams`, `${result.games_imported} games imported`, `${result.games_updated} updated`];
      setSuccess(`${label} complete: ${parts.join(', ')}${result.errors.length ? ` (${result.errors.length} errors)` : ''}`);
      await refreshStatus();
    } catch (err: any) {
      setError(err.response?.data?.detail || `${label} failed`);
    } finally {
      setBusy(false);
    }
  };

  const handleImportTeams = () => runImport(() => adminApi.importTeams(selectedLeague), `${selectedLeague} team import`);

  const handleImportHistorical = () => {
    if (!confirm(`Import ${selectedLeague} games for seasons ${startSeason}-${endSeason}? This may take a while.`)) return;
    return runImport(() => adminApi.importHistorical(selectedLeague, startSeason, endSeason), `${selectedLeague} historical import`);
  };

  const handleSync = () => runImport(() => adminApi.syncLeague(selectedLeague, syncDays), `${selectedLeague} sync`);

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

  if (loading) {
    return <Loading message="Loading admin panel..." />;
  }

  return (
    <Layout>
      <div>
        <h1 className="text-4xl font-bold text-gray-900 mb-8">Admin Dashboard</h1>

        {error && <Alert type="error" message={error} onClose={() => setError('')} />}
        {success && <Alert type="success" message={success} onClose={() => setSuccess('')} />}

        <Card className="mb-8 bg-gradient-to-br from-primary-50 to-white border-primary-100">
          <h2 className="text-2xl font-bold text-primary-700 mb-4">Data Management</h2>
          <div className="mb-6">
            <label className="block text-sm font-bold text-gray-700 mb-2 uppercase tracking-wide">
              League
            </label>
            <select
              value={selectedLeague}
              onChange={(e) => setSelectedLeague(e.target.value)}
              className="w-full max-w-xs px-4 py-3 border border-gray-300 rounded-xl focus:outline-none focus:ring-2 focus:ring-primary-500"
            >
              {leagues.map((league) => (
                <option key={league.code} value={league.code}>
                  {league.name} ({league.code})
                </option>
              ))}
            </select>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
            <div className="p-4 bg-white rounded-xl shadow-sm">
              <p className="text-sm font-bold text-gray-700 mb-3">Import Teams</p>
              <Button onClick={handleImportTeams} disabled={busy || !selectedLeague} className="w-full" size="sm">
                {busy ? 'Working...' : 'Import Teams'}
              </Button>
            </div>

            <div className="p-4 bg-white rounded-xl shadow-sm">
              <p className="text-sm font-bold text-gray-700 mb-3">Import Historical</p>
              <div className="flex gap-2 mb-3">
                <input
                  type="number"
                  value={startSeason}
                  onChange={(e) => setStartSeason(Number(e.target.value))}
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm"
                  aria-label="Start season"
                />
                <input
                  type="number"
                  value={endSeason}
                  onChange={(e) => setEndSeason(Number(e.target.value))}
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm"
                  aria-label="End season"
                />
              </div>
              <Button onClick={handleImportHistorical} disabled={busy || !selectedLeague} className="w-full" size="sm">
                {busy ? 'Working...' : 'Import Historical'}
              </Button>
            </div>

            <div className="p-4 bg-white rounded-xl shadow-sm">
              <p className="text-sm font-bold text-gray-700 mb-3">Sync Recent</p>
              <input
                type="number"
                value={syncDays}
                onChange={(e) => setSyncDays(Number(e.target.value))}
                className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm mb-3"
                aria-label="Days back"
                min={1}
              />
              <Button onClick={handleSync} disabled={busy || !selectedLeague} className="w-full" size="sm">
                {busy ? 'Working...' : `Sync Last ${syncDays}d`}
              </Button>
            </div>
          </div>
        </Card>

        <Card className="mb-8 bg-gradient-to-br from-sage-50 to-white border-sage-100">
          <div className="flex justify-between items-center mb-6">
            <h2 className="text-2xl font-bold text-sage-700">League Status</h2>
            <Button variant="secondary" size="sm" onClick={refreshStatus}>Refresh</Button>
          </div>
          <div className="overflow-x-auto">
            <table className="min-w-full divide-y divide-gray-200">
              <thead>
                <tr>
                  <th className="px-4 py-2 text-left text-xs font-bold text-gray-700 uppercase">League</th>
                  <th className="px-4 py-2 text-left text-xs font-bold text-gray-700 uppercase">Adapter</th>
                  <th className="px-4 py-2 text-left text-xs font-bold text-gray-700 uppercase">Teams</th>
                  <th className="px-4 py-2 text-left text-xs font-bold text-gray-700 uppercase">Games</th>
                  <th className="px-4 py-2 text-left text-xs font-bold text-gray-700 uppercase">Seasons</th>
                </tr>
              </thead>
              <tbody className="bg-white divide-y divide-gray-100">
                {status.map((row) => (
                  <tr key={row.league}>
                    <td className="px-4 py-3 text-sm font-semibold text-gray-900">{row.league}</td>
                    <td className="px-4 py-3 text-sm">
                      {row.adapter_available ? (
                        <span className="text-sage-600 font-medium">Available</span>
                      ) : (
                        <span className="text-gray-400">None</span>
                      )}
                    </td>
                    <td className="px-4 py-3 text-sm text-gray-700">{row.teams}</td>
                    <td className="px-4 py-3 text-sm text-gray-700">{row.games}</td>
                    <td className="px-4 py-3 text-sm text-gray-700">
                      {row.first_season && row.last_season ? `${row.first_season}–${row.last_season}` : '—'}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Card>

        <Card className="mb-8 bg-gradient-to-br from-accent-50 to-white border-accent-100">
          <h2 className="text-2xl font-bold text-accent-700 mb-6">System Statistics</h2>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <div className="flex justify-between items-center p-4 bg-white rounded-xl shadow-sm">
              <span className="text-gray-800 font-medium">Total Users</span>
              <span className="font-bold text-accent-600 text-lg">{users.length}</span>
            </div>
            <div className="flex justify-between items-center p-4 bg-white rounded-xl shadow-sm">
              <span className="text-gray-800 font-medium">Admin Users</span>
              <span className="font-bold text-accent-600 text-lg">
                {users.filter((u) => u.is_admin).length}
              </span>
            </div>
            <div className="flex justify-between items-center p-4 bg-white rounded-xl shadow-sm">
              <span className="text-gray-800 font-medium">Regular Users</span>
              <span className="font-bold text-accent-600 text-lg">
                {users.filter((u) => !u.is_admin).length}
              </span>
            </div>
          </div>
        </Card>

        <Card className="bg-gradient-to-br from-primary-50 to-white border-primary-100">
          <h2 className="text-2xl font-bold text-primary-700 mb-6">User Management</h2>
          <div className="overflow-x-auto">
            <table className="min-w-full divide-y divide-gray-200">
              <thead className="bg-gradient-to-r from-primary-100 to-primary-50">
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
