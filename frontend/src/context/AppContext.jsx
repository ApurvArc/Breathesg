import { useEffect, useMemo, useState } from 'react';
import api from '../configs/api';
import { AuthContext } from './AuthContext';

export const AppProvider = ({ children }) => {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(() => Boolean(localStorage.getItem('access_token')));

  useEffect(() => {
    let active = true;
    const token = localStorage.getItem('access_token');

    if (!token) return undefined;

    api.get('/auth/me/')
      .then(({ data }) => {
        if (active) setUser(data.data);
      })
      .catch(() => {
        localStorage.clear();
      })
      .finally(() => {
        if (active) setLoading(false);
      });

    return () => {
      active = false;
    };
  }, []);

  const login = async (username, password) => {
    const { data } = await api.post('/auth/login/', { username, password });
    localStorage.setItem('access_token', data.access);
    localStorage.setItem('refresh_token', data.refresh);
    const me = await api.get('/auth/me/');
    setUser(me.data.data);
    return me.data.data;
  };

  const logout = () => {
    localStorage.clear();
    setUser(null);
  };

  const value = useMemo(
    () => ({ user, setUser, login, logout, loading }),
    [user, loading],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
};
