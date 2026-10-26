import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";
import Layout from "./components/Layout";
import { Spinner } from "./components/ui";
import "./index.css";
import { AuthProvider, useAuth } from "./lib/auth";
import { LiveProvider } from "./lib/live";
import Audit from "./pages/Audit";
import Dashboard from "./pages/Dashboard";
import Demands from "./pages/Demands";
import Login from "./pages/Login";
import ModelCard from "./pages/ModelCard";
import NewProject from "./pages/NewProject";
import People from "./pages/People";
import Person from "./pages/Person";
import ProjectDetail from "./pages/ProjectDetail";
import Projects from "./pages/Projects";
import Recommend from "./pages/Recommend";

function Guard() {
  const { user, ready } = useAuth();
  if (!ready) return <Spinner />;
  return user ? <Layout /> : <Navigate to="/login" replace />;
}

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <BrowserRouter>
      <AuthProvider>
        <LiveProvider>
          <Routes>
            <Route path="/login" element={<Login />} />
            <Route element={<Guard />}>
              <Route index element={<Dashboard />} />
              <Route path="demands" element={<Demands />} />
              <Route path="demands/:roleId" element={<Recommend />} />
              <Route path="new" element={<NewProject />} />
              <Route path="projects" element={<Projects />} />
              <Route path="projects/:projectId" element={<ProjectDetail />} />
              <Route path="people" element={<People />} />
              <Route path="people/:employeeId" element={<Person />} />
              <Route path="audit" element={<Audit />} />
              <Route path="model" element={<ModelCard />} />
              <Route path="*" element={<Navigate to="/" replace />} />
            </Route>
          </Routes>
        </LiveProvider>
      </AuthProvider>
    </BrowserRouter>
  </StrictMode>,
);
