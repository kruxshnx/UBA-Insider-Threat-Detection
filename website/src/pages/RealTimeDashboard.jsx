import { useState, useEffect } from 'react'
import { Activity, Shield, Users, TrendingUp, AlertTriangle, Clock, User, Mail, Briefcase } from 'lucide-react'
import { fetchUsers, fetchUserRiskProfile, fetchIntegritySummary, fetchRecentTelemetry } from '../services/api'
import RiskBadge from '../components/RiskBadge'
import { GlowCard } from '../components/ui/spotlight-card'

const RealTimeDashboard = () => {
  const [users, setUsers] = useState([])
  const [loading, setLoading] = useState(true)
  const [integrity, setIntegrity] = useState(null)
  const [selectedUser, setSelectedUser] = useState(null)
  const [userProfile, setUserProfile] = useState(null)
  const [lastUpdate, setLastUpdate] = useState(new Date())

  // Fetch users and integrity summary
  const loadData = async () => {
    try {
      const [usersData, integrityData] = await Promise.all([
        fetchUsers(),
        fetchIntegritySummary()
      ])
      
      if (usersData) {
        setUsers(usersData)
      }
      
      if (integrityData) {
        setIntegrity(integrityData)
      }
      
      setLastUpdate(new Date())
      setLoading(false)
    } catch (error) {
      console.error('Error loading dashboard data:', error)
      setLoading(false)
    }
  }

  useEffect(() => {
    loadData()
    const interval = setInterval(loadData, 5000) // Update every 5 seconds
    return () => clearInterval(interval)
  }, [])

  const handleUserClick = async (userId) => {
    if (selectedUser === userId) {
      setSelectedUser(null)
      setUserProfile(null)
      return
    }
    
    setSelectedUser(userId)
    const profile = await fetchUserRiskProfile(userId)
    setUserProfile(profile)
  }

  const getRiskColor = (score) => {
    if (score >= 80) return 'text-red-500'
    if (score >= 60) return 'text-orange-500'
    if (score >= 40) return 'text-yellow-500'
    return 'text-green-500'
  }

  const getRiskBg = (score) => {
    if (score >= 80) return 'bg-red-500/20 border-red-500/50'
    if (score >= 60) return 'bg-orange-500/20 border-orange-500/50'
    if (score >= 40) return 'bg-yellow-500/20 border-yellow-500/50'
    return 'bg-green-500/20 border-green-500/50'
  }

  const getRiskIcon = (score) => {
    if (score >= 80) return '🔴 Critical'
    if (score >= 60) return '🟠 High'
    if (score >= 40) return '🟡 Elevated'
    return '🟢 Normal'
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-screen bg-gradient-to-br from-surface via-surface-light to-surface">
        <div className="text-center">
          <Activity className="w-12 h-12 animate-spin text-primary mx-auto mb-4" />
          <p className="text-lg text-on-surface">Loading real-time data...</p>
        </div>
      </div>
    )
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-surface via-surface-light to-surface p-6">
      {/* Header */}
      <div className="mb-6 flex justify-between items-center">
        <div>
          <h1 className="text-3xl font-bold text-on-surface mb-2">
            Real-Time UBA Dashboard
          </h1>
          <p className="text-on-surface-muted flex items-center gap-2">
            <Clock className="w-4 h-4" />
            Last updated: {lastUpdate.toLocaleTimeString()}
            <button 
              onClick={loadData}
              className="ml-4 px-3 py-1 bg-primary text-on-primary rounded hover:opacity-90 text-sm"
            >
              Refresh
            </button>
          </p>
        </div>
        
        <div className="flex gap-4">
          <GlowCard className="px-4 py-2">
            <div className="text-center">
              <div className="text-2xl font-bold text-on-surface">
                {integrity?.total_users || users.length}
              </div>
              <div className="text-xs text-on-surface-muted">Total Users</div>
            </div>
          </GlowCard>
          
          <GlowCard className="px-4 py-2">
            <div className="text-center">
              <div className="text-2xl font-bold text-green-500">
                {integrity?.in_zone || 0}
              </div>
              <div className="text-xs text-on-surface-muted">In Zone</div>
            </div>
          </GlowCard>
          
          <GlowCard className="px-4 py-2">
            <div className="text-center">
              <div className="text-2xl font-bold text-yellow-500">
                {integrity?.anomalous || 0}
              </div>
              <div className="text-xs text-on-surface-muted">Anomalous</div>
            </div>
          </GlowCard>
          
          <GlowCard className="px-4 py-2">
            <div className="text-center">
              <div className="text-2xl font-bold text-red-500">
                {integrity?.critical || 0}
              </div>
              <div className="text-xs text-on-surface-muted">Critical</div>
            </div>
          </GlowCard>
        </div>
      </div>

      {/* Main Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Users List */}
        <div className="lg:col-span-2">
          <GlowCard className="p-6 h-full">
            <h2 className="text-xl font-bold text-on-surface mb-4 flex items-center gap-2">
              <Users className="w-5 h-5" />
              Employee Monitoring
            </h2>
            
            <div className="space-y-3">
              {users.map((user) => (
                <div
                  key={user.user_id}
                  onClick={() => handleUserClick(user.user_id)}
                  className={`p-4 rounded-lg border transition-all cursor-pointer ${
                    selectedUser === user.user_id 
                      ? 'border-primary bg-primary/10' 
                      : 'border-surface-variant hover:border-primary/50'
                  }`}
                >
                  <div className="flex justify-between items-center">
                    <div className="flex items-center gap-3">
                      <div className={`w-3 h-3 rounded-full ${
                        user.risk_score >= 80 ? 'bg-red-500' :
                        user.risk_score >= 60 ? 'bg-orange-500' :
                        user.risk_score >= 40 ? 'bg-yellow-500' : 'bg-green-500'
                      }`} />
                      
                      <div>
                        <div className="flex items-center gap-2">
                          <h3 className="font-semibold text-on-surface">{user.name}</h3>
                          <span className="text-xs px-2 py-0.5 bg-surface-variant rounded text-on-surface-muted">
                            {user.user_id}
                          </span>
                        </div>
                        <div className="flex items-center gap-3 text-sm text-on-surface-muted mt-1">
                          <span className="flex items-center gap-1">
                            <Briefcase className="w-3 h-3" />
                            {user.role}
                          </span>
                          <span className="flex items-center gap-1">
                            <Mail className="w-3 h-3" />
                            {user.department}
                          </span>
                        </div>
                      </div>
                    </div>
                    
                    <div className="text-right">
                      <div className={`text-2xl font-bold ${getRiskColor(user.risk_score || 0)}`}>
                        {user.risk_score?.toFixed(1) || 0}
                      </div>
                      <div className="text-xs text-on-surface-muted">
                        {getRiskIcon(user.risk_score || 0)}
                      </div>
                      <div className="text-xs text-on-surface-muted mt-1">
                        Prod: {((user.productivity_score || 0) * 100).toFixed(0)}%
                      </div>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </GlowCard>
        </div>

        {/* User Details Panel */}
        <div className="lg:col-span-1">
          <GlowCard className="p-6 h-full">
            {selectedUser && userProfile ? (
              <div>
                <h2 className="text-xl font-bold text-on-surface mb-4 flex items-center gap-2">
                  <User className="w-5 h-5" />
                  User Profile
                </h2>
                
                <div className="space-y-4">
                  <div>
                    <h3 className="font-semibold text-on-surface text-lg">{userProfile.name}</h3>
                    <p className="text-sm text-on-surface-muted">{userProfile.role} - {userProfile.department}</p>
                    <p className="text-xs text-on-surface-muted mt-1">ID: {userProfile.user_id}</p>
                  </div>
                  
                  <div className="grid grid-cols-2 gap-3">
                    <div className={`p-3 rounded-lg border ${getRiskBg(userProfile.current_risk)}`}>
                      <div className="text-xs text-on-surface-muted">Current Risk</div>
                      <div className={`text-2xl font-bold ${getRiskColor(userProfile.current_risk)}`}>
                        {userProfile.current_risk?.toFixed(1)}
                      </div>
                    </div>
                    
                    <div className="p-3 rounded-lg border border-surface-variant">
                      <div className="text-xs text-on-surface-muted">Productivity</div>
                      <div className="text-2xl font-bold text-on-surface">
                        {((userProfile.current_productivity || 0) * 100).toFixed(0)}%
                      </div>
                    </div>
                  </div>
                  
                  <div className="space-y-2">
                    <div className="flex justify-between text-sm">
                      <span className="text-on-surface-muted">Avg Risk (24h):</span>
                      <span className="text-on-surface font-medium">{userProfile.avg_risk_24h?.toFixed(1)}</span>
                    </div>
                    <div className="flex justify-between text-sm">
                      <span className="text-on-surface-muted">Max Risk (24h):</span>
                      <span className="text-on-surface font-medium">{userProfile.max_risk_24h?.toFixed(1)}</span>
                    </div>
                    <div className="flex justify-between text-sm">
                      <span className="text-on-surface-muted">Telemetry Count:</span>
                      <span className="text-on-surface font-medium">{userProfile.telemetry_count}</span>
                    </div>
                    <div className="flex justify-between text-sm">
                      <span className="text-on-surface-muted">Status:</span>
                      <span className={`font-medium capitalize ${userProfile.status === 'active' ? 'text-green-500' : 'text-gray-500'}`}>
                        {userProfile.status}
                      </span>
                    </div>
                  </div>
                  
                  {userProfile.last_seen && (
                    <div className="text-xs text-on-surface-muted">
                      Last seen: {new Date(userProfile.last_seen).toLocaleString()}
                    </div>
                  )}
                </div>
              </div>
            ) : (
              <div className="h-full flex items-center justify-center text-center text-on-surface-muted">
                <div>
                  <User className="w-12 h-12 mx-auto mb-2 opacity-50" />
                  <p>Select a user to view details</p>
                </div>
              </div>
            )}
          </GlowCard>
        </div>
      </div>

      {/* Risk Breakdown Table */}
      <div className="mt-6">
        <GlowCard className="p-6">
          <h2 className="text-xl font-bold text-on-surface mb-4 flex items-center gap-2">
            <TrendingUp className="w-5 h-5" />
            Real-Time Risk Analysis
          </h2>
          
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead>
                <tr className="border-b border-surface-variant">
                  <th className="text-left py-3 px-4 text-sm font-semibold text-on-surface-muted">User</th>
                  <th className="text-left py-3 px-4 text-sm font-semibold text-on-surface-muted">Role</th>
                  <th className="text-center py-3 px-4 text-sm font-semibold text-on-surface-muted">Risk Score</th>
                  <th className="text-center py-3 px-4 text-sm font-semibold text-on-surface-muted">Productivity</th>
                  <th className="text-left py-3 px-4 text-sm font-semibold text-on-surface-muted">Status</th>
                  <th className="text-left py-3 px-4 text-sm font-semibold text-on-surface-muted">Last Update</th>
                </tr>
              </thead>
              <tbody>
                {users.map((user) => (
                  <tr key={user.user_id} className="border-b border-surface-variant/50 hover:bg-surface-variant/20">
                    <td className="py-3 px-4">
                      <div className="flex items-center gap-2">
                        <div className={`w-2 h-2 rounded-full ${
                          user.risk_score >= 80 ? 'bg-red-500' :
                          user.risk_score >= 60 ? 'bg-orange-500' :
                          user.risk_score >= 40 ? 'bg-yellow-500' : 'bg-green-500'
                        }`} />
                        <span className="text-on-surface">{user.name}</span>
                      </div>
                    </td>
                    <td className="py-3 px-4 text-on-surface-muted">{user.role}</td>
                    <td className="py-3 px-4 text-center">
                      <span className={`font-bold ${getRiskColor(user.risk_score || 0)}`}>
                        {user.risk_score?.toFixed(1) || '0.0'}
                      </span>
                    </td>
                    <td className="py-3 px-4 text-center">
                      <span className="text-on-surface">
                        {((user.productivity_score || 0) * 100).toFixed(0)}%
                      </span>
                    </td>
                    <td className="py-3 px-4">
                      <span className={`px-2 py-1 rounded text-xs font-medium ${
                        (user.risk_score || 0) >= 80 ? 'bg-red-500/20 text-red-500' :
                        (user.risk_score || 0) >= 60 ? 'bg-orange-500/20 text-orange-500' :
                        (user.risk_score || 0) >= 40 ? 'bg-yellow-500/20 text-yellow-500' : 'bg-green-500/20 text-green-500'
                      }`}>
                        {getRiskIcon(user.risk_score || 0)}
                      </span>
                    </td>
                    <td className="py-3 px-4 text-sm text-on-surface-muted">
                      {user.last_seen ? new Date(user.last_seen).toLocaleString() : 'Never'}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </GlowCard>
      </div>
    </div>
  )
}

export default RealTimeDashboard
