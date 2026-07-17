import React, { useState } from 'react';
import { Link } from 'react-router-dom';
import { authApi } from '../api/auth';
import Button from '../components/common/Button';
import Input from '../components/common/Input';
import Card from '../components/common/Card';
import Alert from '../components/common/Alert';

const ForgotPassword: React.FC = () => {
  const [email, setEmail] = useState('');
  const [submitted, setSubmitted] = useState(false);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    setLoading(true);
    try {
      await authApi.forgotPassword(email);
      setSubmitted(true);
    } catch {
      setError('Something went wrong. Please try again.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-primary-50 via-white to-sage-50 flex items-center justify-center px-4">
      <div className="max-w-md w-full">
        <div className="text-center mb-10">
          <h1 className="text-4xl font-bold text-primary-700 mb-3">SportsPassport2</h1>
          <p className="text-lg text-gray-700 font-medium">Reset your password</p>
        </div>

        <Card className="bg-gradient-to-br from-white to-gray-50 shadow-elevated">
          <h2 className="text-3xl font-bold mb-8 text-gray-900">Forgot password</h2>

          {submitted ? (
            <div>
              <Alert
                type="success"
                message="If that email is registered, a reset link has been sent. Check your inbox."
              />
              <p className="mt-6 text-center text-sm text-gray-700">
                <Link to="/login" className="text-primary-600 hover:text-primary-700 font-bold">
                  ← Back to sign in
                </Link>
              </p>
            </div>
          ) : (
            <>
              {error && <Alert type="error" message={error} onClose={() => setError('')} />}

              <form onSubmit={handleSubmit} className="space-y-6">
                <Input
                  label="Email"
                  type="email"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  placeholder="you@example.com"
                  autoComplete="email"
                  required
                />

                <Button type="submit" className="w-full" disabled={loading}>
                  {loading ? 'Sending...' : 'Send reset link'}
                </Button>
              </form>

              <p className="mt-6 text-center text-sm text-gray-700">
                <Link to="/login" className="text-primary-600 hover:text-primary-700 font-bold">
                  ← Back to sign in
                </Link>
              </p>
            </>
          )}
        </Card>
      </div>
    </div>
  );
};

export default ForgotPassword;
