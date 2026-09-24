import { NavLink, Route, Routes, useNavigate } from "react-router-dom";
import { clearAuth, currentUser } from "./lib/api";
import Home from "./pages/Home.jsx";
import Problems from "./pages/Problems.jsx";
import Problem from "./pages/Problem.jsx";
import Auth from "./pages/Auth.jsx";
import Contests from "./pages/Contests.jsx";
import Contest from "./pages/Contest.jsx";
import Assessments from "./pages/Assessments.jsx";
import Assessment from "./pages/Assessment.jsx";
import Submissions from "./pages/Submissions.jsx";
import Metrics from "./pages/Metrics.jsx";

function Nav() {
  const nav = useNavigate();
  const user = currentUser();
  return (
    <header className="nav">
      <NavLink to="/" className="brand">
        <span className="mark" />
        Aether
      </NavLink>
      <nav className="nav-links">
        <NavLink to="/problems">Problems</NavLink>
        <NavLink to="/contests">Contests</NavLink>
        <NavLink to="/assessments">Assessments</NavLink>
        <NavLink to="/submissions">History</NavLink>
        <NavLink to="/metrics">Observability</NavLink>
      </nav>
      <div className="nav-cta">
        {user ? (
          <>
            <span className="pill">{user.username}</span>
            <button
              className="btn ghost"
              onClick={() => {
                clearAuth();
                nav("/");
              }}
            >
              Sign out
            </button>
          </>
        ) : (
          <>
            <NavLink to="/login" className="btn ghost">
              Sign in
            </NavLink>
            <NavLink to="/register" className="btn gold">
              Create account
            </NavLink>
          </>
        )}
      </div>
    </header>
  );
}

export default function App() {
  return (
    <div className="app">
      <Nav />
      <Routes>
        <Route path="/" element={<Home />} />
        <Route path="/problems" element={<Problems />} />
        <Route path="/problems/:slug" element={<Problem />} />
        <Route path="/login" element={<Auth mode="login" />} />
        <Route path="/register" element={<Auth mode="register" />} />
        <Route path="/contests" element={<Contests />} />
        <Route path="/contests/:slug" element={<Contest />} />
        <Route path="/assessments" element={<Assessments />} />
        <Route path="/assessments/:slug" element={<Assessment />} />
        <Route path="/submissions" element={<Submissions />} />
        <Route path="/metrics" element={<Metrics />} />
      </Routes>
    </div>
  );
}
