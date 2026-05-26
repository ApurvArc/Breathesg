import { createContext, useContext } from 'react';

export const AuthContext = createContext(null);

export const useAppContext = () => useContext(AuthContext);
