import React, { Suspense, lazy } from 'react'
import ReactDOM from 'react-dom/client'
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import AppLayout from './components/AppLayout'
import './index.css'

const Dashboard = lazy(() => import('./pages/Dashboard'))
const SessionsList = lazy(() => import('./pages/SessionsList'))
const SessionDetail = lazy(() => import('./pages/SessionDetail'))
const AudioUpload = lazy(() => import('./pages/AudioUpload'))
const LiveListen = lazy(() => import('./pages/LiveListen'))
const DeviceManage = lazy(() => import('./pages/DeviceManage'))
const ReviewFeed = lazy(() => import('./pages/ReviewFeed'))
const Login = lazy(() => import('./pages/Login'))
const Register = lazy(() => import('./pages/Register'))

function PrivateRoute({ children }) {
  const token = localStorage.getItem('access_token')
  return token ? children : <Navigate to="/login" replace />
}

ReactDOM.createRoot(document.getElementById('root')).render(
  <React.StrictMode>
    <BrowserRouter>
      <Suspense fallback={<div className="app-shell-loading">加载中...</div>}>
        <Routes>
          <Route path="/login" element={<Login />} />
          <Route path="/register" element={<Register />} />
          <Route path="/" element={<PrivateRoute><AppLayout /></PrivateRoute>}>
            <Route index element={<Navigate to="/dashboard" replace />} />
            <Route path="dashboard" element={<Dashboard />} />
            <Route path="sessions" element={<SessionsList />} />
            <Route path="sessions/:id" element={<SessionDetail />} />
            <Route path="upload" element={<AudioUpload />} />
            <Route path="live" element={<LiveListen />} />
            <Route path="devices" element={<DeviceManage />} />
            <Route path="review" element={<ReviewFeed />} />
          </Route>
        </Routes>
      </Suspense>
    </BrowserRouter>
  </React.StrictMode>,
)
