import React, { useState } from 'react';
import { useAuth } from '../hooks/useAuth';
import { authApi } from '../api/auth';
import Layout from '../components/layout/Layout';
import Card from '../components/common/Card';
import Input from '../components/common/Input';
import Button from '../components/common/Button';
import Alert from '../components/common/Alert';

const Profile: React.FC = () => {
  const { user } = useAuth();
  const [currentPassword, setCurrentPassword] = useState('');
  const [newPassword, setNewPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');
  const [submitting, setSubmitting] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    setSuccess('');

    if (newPassword !== confirmPassword) {
      setError('New passwords do not match.');
      return;
    }
    if (newPassword.length < 8) {
      setError('New password must be at least 8 characters.');
      return;
    }

    setSubmitting(true);
    try {
      await authApi.changePassword(currentPassword, newPassword);
      setSuccess('Password updated successfully.');
      setCurrentPassword('');
      setNewPassword('');
      setConfirmPassword('');
    } catch (err: any) {
      const detail = err.response?.data?.detail;
      setError(
        detail === 'Current password is incorrect'
          ? 'Current password is incorrect.'
          : detail || 'Failed to update password.'
      );
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <Layout>
      <div className="max-w-md mx-auto">
        <div className="mb-8">
          <h1 className="text-3xl font-bold text-gray-900">My Profile</h1>
          <p className="text-gray-700 mt-1">Manage your account settings</p>
        </div>

        <Card className="bg-gradient-to-br from-white to-gray-50 shadow-elevated mb-6">
          <div className="text-sm font-bold text-gray-700 uppercase tracking-wide mb-1">Name</div>
          <div className="text-lg text-gray-900 mb-4">{user?.full_name}</div>
          <div className="text-sm font-bold text-gray-700 uppercase tracking-wide mb-1">Email</div>
          <div className="text-lg text-gray-900">{user?.email}</div>
        </Card>

        <Card className="bg-gradient-to-br from-white to-gray-50 shadow-elevated">
          <h2 className="text-xl font-bold mb-6 text-gray-900">Change Password</h2>

          {error && <Alert type="error" message={error} onClose={() => setError('')} />}
          {success && <Alert type="success" message={success} onClose={() => setSuccess('')} />}

          <form onSubmit={handleSubmit} className="space-y-6">
            <Input
              label="Current Password"
              type="password"
              value={currentPassword}
              onChange={(e) => setCurrentPassword(e.target.value)}
              placeholder="Enter current password"
              autoComplete="current-password"
              required
            />

            <Input
              label="New Password"
              type="password"
              value={newPassword}
              onChange={(e) => setNewPassword(e.target.value)}
              placeholder="Enter new password"
              autoComplete="new-password"
              minLength={8}
              required
            />

            <Input
              label="Confirm New Password"
              type="password"
              value={confirmPassword}
              onChange={(e) => setConfirmPassword(e.target.value)}
              placeholder="Confirm new password"
              autoComplete="new-password"
              required
            />

            <Button type="submit" className="w-full" disabled={submitting}>
              {submitting ? 'Saving...' : 'Update Password'}
            </Button>
          </form>
        </Card>
      </div>
    </Layout>
  );
};

export default Profile;
