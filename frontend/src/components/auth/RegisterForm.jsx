import { useState } from 'react';
import { useForm } from 'react-hook-form';
import { Link, useNavigate } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { useAuth } from '../../context/AuthContext';

const RegisterForm = () => {
  const { t } = useTranslation();
  const { register, handleSubmit, watch, formState: { errors } } = useForm();
  const { register: registerUser } = useAuth();
  const navigate = useNavigate();
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  const password = watch('password');

  const onSubmit = async (data) => {
    setLoading(true);
    setError('');
    try {
      await registerUser({
        email: data.email,
        password: data.password,
        salon_name: data.salon_name,
      });
      navigate('/dashboard');
    } catch (err) {
      setError(err.response?.data?.message || t('auth.registrationFailed'));
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="w-full max-w-md">
      <div className="card">
        <h2 className="text-2xl font-bold text-center mb-2">{t('auth.createAccount')}</h2>
        <p className="text-center text-gray-600 mb-6">{t('auth.trialNotice')}</p>

        {error && (
          <div className="bg-red-50 text-red-600 p-3 rounded-lg mb-4">
            {error}
          </div>
        )}

        <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
          <div>
            <label className="block text-sm font-medium mb-2">{t('auth.salonName')}</label>
            <input
              type="text"
              className="input"
              placeholder={t('auth.salonName')}
              {...register('salon_name', { required: t('auth.salonNameRequired') })}
            />
            {errors.salon_name && (
              <p className="text-red-500 text-sm mt-1">{errors.salon_name.message}</p>
            )}
          </div>

          <div>
            <label className="block text-sm font-medium mb-2">{t('auth.email')}</label>
            <input
              type="email"
              className="input"
              placeholder={t('auth.email')}
              {...register('email', {
                required: t('auth.emailRequired'),
                pattern: {
                  value: /^[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}$/i,
                  message: t('auth.invalidEmail')
                }
              })}
            />
            {errors.email && (
              <p className="text-red-500 text-sm mt-1">{errors.email.message}</p>
            )}
          </div>

          <div>
            <label className="block text-sm font-medium mb-2">{t('auth.password')}</label>
            <input
              type="password"
              className="input"
              placeholder={t('auth.passwordMin')}
              {...register('password', {
                required: t('auth.passwordRequired'),
                minLength: {
                  value: 8,
                  message: t('auth.passwordMin')
                }
              })}
            />
            {errors.password && (
              <p className="text-red-500 text-sm mt-1">{errors.password.message}</p>
            )}
          </div>

          <div>
            <label className="block text-sm font-medium mb-2">{t('auth.confirmPassword')}</label>
            <input
              type="password"
              className="input"
              {...register('confirm_password', {
                required: t('auth.confirmPasswordRequired'),
                validate: value => value === password || t('auth.passwordsMustMatch')
              })}
            />
            {errors.confirm_password && (
              <p className="text-red-500 text-sm mt-1">{errors.confirm_password.message}</p>
            )}
          </div>

          <button
            type="submit"
            disabled={loading}
            className="w-full btn-primary"
          >
            {loading ? t('auth.creatingAccount') : t('auth.registerButton')}
          </button>
        </form>

        <div className="mt-6 text-center text-sm">
          <span className="text-gray-600">{t('auth.hasAccount')} </span>
          <Link to="/login" className="text-primary-500 hover:underline font-medium">
            {t('auth.loginButton')}
          </Link>
        </div>

        <p className="mt-4 text-xs text-center text-gray-500">
          {t('auth.trialNotice')}
        </p>
      </div>
    </div>
  );
};

export default RegisterForm;
