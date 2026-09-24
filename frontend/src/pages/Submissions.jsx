import { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { api, currentUser } from "../lib/api";

export default function Submissions() {
  const nav = useNavigate();
  const [rows, setRows] = useState([]);
  useEffect(() => {
    if (!currentUser()) {
      nav("/login");
      return;
    }
    api("/api/submissions").then(setRows).catch(() => setRows([]));
  }, []);
  return (
    <div className="page">
      <div className="eyebrow">Trail</div>
      <h1>Submissions</h1>
      <table className="table">
        <thead>
          <tr>
            <th>ID</th>
            <th>Problem</th>
            <th>Lang</th>
            <th>Verdict</th>
            <th>Runtime</th>
            <th>When</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((s) => (
            <tr key={s.id}>
              <td className="mono">{s.id}</td>
              <td>
                <Link to={`/problems/${s.problem_id}`}>{s.problem_title || s.problem_id}</Link>
              </td>
              <td className="mono">{s.language}</td>
              <td className={`verdict ${s.verdict === "Accepted" ? "v-Accepted" : "v-Wrong"}`}>{s.verdict}</td>
              <td className="mono">{s.runtime_ms} ms</td>
              <td className="mono">{new Date(s.created_at).toLocaleString()}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
