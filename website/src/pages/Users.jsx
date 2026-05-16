import { useState, useEffect } from 'react'
import { fetchUsers } from '../services/api'
import { Users as UsersIcon, Search, AlertTriangle, Mail, Briefcase } from 'lucide-react'

export default function Users() {
  const [users, setUsers] = useState([])
  const [loading, setLoading] = useState(true)
  const [searchTerm, setSearchTerm] = useState('')
  const [roleFilter, setRoleFilter] = useState('All')

  useEffect(() => {
    const loadData = async () => {
      try {
        const data = await fetchUsers()
        setUsers(data || [])
        setLoading(false)
      } catch (error) {
        console.error('Error loading users:', error)
        setLoading(false)
      }
    }
    loadData()
    const interval = setInterval(loadData, 5000)
    return () => clearInterval(interval)
  }, [])

  const filteredUsers = users.filter(user => {
    const matchesSearch = user.name.toLowerCase().includes(searchTerm.toLowerCase()) ||
                         user.user_id.toLowerCase().includes(searchTerm.toLowerCase())
    const matchesRole = roleFilter === 'All' || user.role === roleFilter
    return matchesSearch && matchesRole
  })

  const roles = ['All', ...new Set(users.map(u => u.role))]

  const getRiskColor = (score) => {
    if (score >= 80) return 'text-red-500'
    if (score >= 60) return 'text-orange-500'
    if (score >= 40) return 'text-yellow-500'
    return 'text-green-500'
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center h-full">
        <div className="text-center text-on-surface">
          <p>Loading users...</p>
        </div>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-on-surface">User Management</h1>
        <p className="text-on-surface-muted mt-1">Monitor and manage employee accounts</p>
      </div>

      {/* Filters */}
      <div className="flex gap-4">
        <div className="flex-1 relative">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-on-surface-muted" />
          <input
            type="text"
            placeholder="Search users..."
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            className="w-full pl-10 pr-4 py-2 bg-surface border border-surface-variant rounded text-on-surface focus:outline-none focus:border-primary/50"
          />
        </div>
        <select
          value={roleFilter}
          onChange={(e) => setRoleFilter(e.target.value)}
          className="px-4 py-2 bg-surface border border-surface-variant rounded text-on-surface focus:outline-none focus:border-primary/50"
        >
          {roles.map(role => (
            <option key={role} value={role}>{role}</option>
          ))}
        </select>
      </div>

      {/* Users Grid */}
      <div className="grid gap-4">
        {filteredUsers.length === 0 ? (
          <div className="bg-surface rounded-lg p-12 border border-surface-variant text-center">
            <AlertTriangle className="w-12 h-12 mx-auto mb-4 text-on-surface-muted opacity-50" />
            <h3 className="text-lg font-semibold text-on-surface mb-2">No users found</h3>
            <p className="text-on-surface-muted">Try adjusting your search or filter</p>
          </div>
        ) : (
          filteredUsers.map((user) => (
            <div key={user.user_id} className="bg-surface rounded-lg p-4 border border-surface-variant">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-4">
                  <div className={`w-10 h-10 rounded-full flex items-center justify-center ${
                    user.risk_score >= 80 ? 'bg-red-500/20' :
                    user.risk_score >= 60 ? 'bg-orange-500/20' :
                    user.risk_score >= 40 ? 'bg-yellow-500/20' : 'bg-green-500/20'
                  }`}>
                    <UsersIcon className={`w-5 h-5 ${
                      user.risk_score >= 80 ? 'text-red-500' :
                      user.risk_score >= 60 ? 'text-orange-500' :
                      user.risk_score >= 40 ? 'text-yellow-500' : 'text-green-500'
                    }`} />
                  </div>
                  <div>
                    <h3 className="font-semibold text-on-surface">{user.name}</h3>
                    <div className="flex items-center gap-3 text-sm text-on-surface-muted mt-1">
                      <span className="flex items-center gap-1">
                        <Briefcase className="w-3 h-3" />
                        {user.role}
                      </span>
                      <span className="flex items-center gap-1">
                        <Mail className="w-3 h-3" />
                        {user.email}
                      </span>
                    </div>
                  </div>
                </div>
                <div className="text-right">
                  <div className={`text-2xl font-bold ${getRiskColor(user.risk_score || 0)}`}>
                    {(user.risk_score || 0).toFixed(1)}
                  </div>
                  <div className="text-xs text-on-surface-muted">Risk Score</div>
                  <div className="text-xs text-on-surface-muted mt-1">
                    Prod: {((user.productivity_score || 0) * 100).toFixed(0)}%
                  </div>
                </div>
              </div>
            </div>
          ))
        )}
      </div>

      {/* Stats */}
      <div className="grid grid-cols-4 gap-4">
        <div className="bg-surface rounded-lg p-4 border border-surface-variant text-center">
          <div className="text-2xl font-bold text-on-surface">{users.length}</div>
          <div className="text-xs text-on-surface-muted">Total Users</div>
        </div>
        <div className="bg-surface rounded-lg p-4 border border-surface-variant text-center">
          <div className="text-2xl font-bold text-green-500">{users.filter(u => u.is_active).length}</div>
          <div className="text-xs text-on-surface-muted">Active</div>
        </div>
        <div className="bg-surface rounded-lg p-4 border border-surface-variant text-center">
          <div className="text-2xl font-bold text-yellow-500">{users.filter(u => (u.risk_score || 0) >= 40).length}</div>
          <div className="text-xs text-on-surface-muted">Elevated Risk</div>
        </div>
        <div className="bg-surface rounded-lg p-4 border border-surface-variant text-center">
          <div className="text-2xl font-bold text-red-500">{users.filter(u => (u.risk_score || 0) >= 80).length}</div>
          <div className="text-xs text-on-surface-muted">Critical</div>
        </div>
      </div>
    </div>
  )
}