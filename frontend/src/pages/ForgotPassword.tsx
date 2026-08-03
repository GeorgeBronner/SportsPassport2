import React, { useState } from 'react';
import { Link } from 'react-router-dom';
import { authApi } from '../api/auth';
import Button from '../components/common/Button';
import Input from '../components/common/Input';
import Alert from '../components/common/Alert';
import AuthShell from '../components/layout/AuthShell';

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

  const backToSignIn = (
    <p className="mt-4 text-center text-sm text-ink-2">
      <Link to="/login" className="text-focus hover:underline font-semibold">
        ← Back to sign in
      </Link>
    </p>
  );

  return (
    <AuthShell tagline="Reset your password" title="Forgot password">
      {submitted ? (
        <>
          <Alert
            type="success"
            message="If that email is registered, a reset link has been sent. Check your inbox."
          />
          {backToSignIn}
        </>
      ) : (
        <>
          {error && <Alert type="error" message={error} onClose={() => setError('')} />}

          <form onSubmit={handleSubmit}>
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

          {backToSignIn}
        </>
      )}
    </AuthShell>
  );
};

export default ForgotPassword;
