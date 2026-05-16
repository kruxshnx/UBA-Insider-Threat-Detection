/**
 * Telemetry API Service
 * Handles communication with real-time telemetry backend
 */

import { api } from './api'

/**
 * Fetch global integrity summary
 */
export const fetchIntegritySummary = async () => {
  try {
    const response = await api.get('/api/v1/telemetry/integrity/summary')
    return response.data
  } catch (error) {
    console.error('Error fetching integrity summary:', error)
    return null
  }
}

/**
 * Fetch user telemetry data
 */
export const fetchUserTelemetry = async (userId, limit = 100) => {
  try {
    const response = await api.get(`/api/v1/telemetry/user/${userId}?limit=${limit}`)
    return response.data
  } catch (error) {
    console.error('Error fetching user telemetry:', error)
    return null
  }
}

/**
 * Fetch recent telemetry across all users
 */
export const fetchRecentTelemetry = async (limit = 100) => {
  try {
    const response = await api.get(`/api/v1/telemetry/recent?limit=${limit}`)
    return response.data
  } catch (error) {
    console.error('Error fetching recent telemetry:', error)
    return null
  }
}

/**
 * Get user baseline
 */
export const fetchUserBaseline = async (userId) => {
  try {
    const response = await api.get(`/api/v1/telemetry/user/${userId}/baseline`)
    return response.data
  } catch (error) {
    console.error('Error fetching user baseline:', error)
    return null
  }
}

/**
 * Update user baseline
 */
export const updateUserBaseline = async (userId, windowDays = 7) => {
  try {
    const response = await api.post(
      `/api/v1/telemetry/user/${userId}/baseline/update?window_days=${windowDays}`
    )
    return response.data
  } catch (error) {
    console.error('Error updating user baseline:', error)
    return null
  }
}

/**
 * Send telemetry data (for agent)
 */
export const sendTelemetry = async (telemetryData) => {
  try {
    const response = await api.post('/api/v1/telemetry/', telemetryData)
    return response.data
  } catch (error) {
    console.error('Error sending telemetry:', error)
    return null
  }
}
