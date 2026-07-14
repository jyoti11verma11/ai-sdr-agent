import React, { createContext, useContext, useEffect, useState } from "react";
import api from "./api";

const AuthCtx = createContext(null);

export function AuthProvider({ children }) {
  const [user, setUser] = useState(() => {
    try { return JSON.parse(localStorage.getItem("sdr_user") || "null"); } catch { return null; }
  });
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const token = localStorage.getItem("sdr_token");
    if (!token) { setLoading(false); return; }
    api.get("/auth/me")
      .then((r) => { setUser(r.data); localStorage.setItem("sdr_user", JSON.stringify(r.data)); })
      .catch(() => { localStorage.removeItem("sdr_token"); localStorage.removeItem("sdr_user"); setUser(null); })
      .finally(() => setLoading(false));
  }, []);

  const login = async (email, password) => {
    const { data } = await api.post("/auth/login", { email, password });
    localStorage.setItem("sdr_token", data.token);
    localStorage.setItem("sdr_user", JSON.stringify(data.user));
    setUser(data.user);
    return data.user;
  };

  const signup = async (email, password, full_name) => {
    const { data } = await api.post("/auth/signup", { email, password, full_name });
    localStorage.setItem("sdr_token", data.token);
    localStorage.setItem("sdr_user", JSON.stringify(data.user));
    setUser(data.user);
    return data.user;
  };

  const logout = () => {
    localStorage.removeItem("sdr_token");
    localStorage.removeItem("sdr_user");
    setUser(null);
  };

  return (
    <AuthCtx.Provider value={{ user, login, signup, logout, loading }}>
      {children}
    </AuthCtx.Provider>
  );
}

export const useAuth = () => useContext(AuthCtx);
