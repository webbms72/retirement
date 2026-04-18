import axios from 'axios';

const api = axios.create({
  baseURL: '/api',
  headers: { 'Content-Type': 'application/json' },
});

export async function getProfiles() {
  const { data } = await api.get('/profiles/');
  return data;
}

export async function getProfile(id) {
  const { data } = await api.get(`/profiles/${id}`);
  return data;
}

export async function updateProfile(id, payload) {
  const { data } = await api.put(`/profiles/${id}`, payload);
  return data;
}

export async function getAccounts(ownerId) {
  const params = ownerId ? { owner_id: ownerId } : {};
  const { data } = await api.get('/accounts/', { params });
  return data;
}

export async function createAccount(payload) {
  const { data } = await api.post('/accounts/', payload);
  return data;
}

export async function updateAccount(id, payload) {
  const { data } = await api.put(`/accounts/${id}`, payload);
  return data;
}

export async function deleteAccount(id) {
  await api.delete(`/accounts/${id}`);
}

export async function getSocialSecurity(profileId) {
  const { data } = await api.get(`/profiles/${profileId}/social-security`);
  return data;
}

export async function createSocialSecurity(profileId, payload) {
  const { data } = await api.post(`/profiles/${profileId}/social-security`, payload);
  return data;
}

export async function updateSocialSecurity(profileId, payload) {
  const { data } = await api.put(`/profiles/${profileId}/social-security`, payload);
  return data;
}

export async function getScenarios() {
  const { data } = await api.get('/scenarios/');
  return data;
}

export async function createScenario(payload) {
  const { data } = await api.post('/scenarios/', payload);
  return data;
}

export async function updateScenario(id, payload) {
  const { data } = await api.put(`/scenarios/${id}`, payload);
  return data;
}

export async function deleteScenario(id) {
  await api.delete(`/scenarios/${id}`);
}

export async function duplicateScenario(id) {
  const { data } = await api.post(`/scenarios/${id}/duplicate`);
  return data;
}

export async function runProjection(scenarioId) {
  const { data } = await api.post(`/projections/${scenarioId}/run`);
  return data;
}

export async function getProjection(scenarioId) {
  const { data } = await api.get(`/projections/${scenarioId}`);
  return data;
}

export async function runMonteCarlo(scenarioId, numSimulations = 10000) {
  const { data } = await api.post(`/monte-carlo/${scenarioId}/run`, {
    num_simulations: numSimulations,
  });
  return data;
}

export async function getMonteCarlo(scenarioId) {
  const { data } = await api.get(`/monte-carlo/${scenarioId}`);
  return data;
}

export async function getSsStrategies(params) {
  const { data } = await api.get('/ss-optimizer', { params });
  return data;
}

export default api;
