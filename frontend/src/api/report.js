import service from './index'

/**
 * 开始报告生成
 * @param {Object} data - { simulation_id, force_regenerate? }
 */
export const generateReport = (data) => {
  return service.post('/api/report/generate', data)
}

/**
 * 获取报告生成状态
 * @param {string} reportId
 */
export const getReportStatus = (reportId) => {
  return service.get(`/api/report/generate/status`, { params: { report_id: reportId } })
}

/**
 * 获取 Agent 日志（增量）
 * @param {string} reportId
 * @param {number} fromLine - 从第几行开始获取
 */
export const getAgentLog = (reportId, fromLine = 0) => {
  return service.get(`/api/report/${reportId}/agent-log`, { params: { from_line: fromLine } })
}

/**
 * 获取控制台日志（增量）
 * @param {string} reportId
 * @param {number} fromLine - 从第几行开始获取
 */
export const getConsoleLog = (reportId, fromLine = 0) => {
  return service.get(`/api/report/${reportId}/console-log`, { params: { from_line: fromLine } })
}

/**
 * 获取报告详情
 * @param {string} reportId
 */
export const getReport = (reportId) => {
  return service.get(`/api/report/${reportId}`)
}

/**
 * 与 Report Agent 对话
 * @param {Object} data - { simulation_id, message, chat_history? }
 */
export const chatWithReport = (data) => {
  return service.post('/api/report/chat', data)
}

/**
 * 获取报告生成进度（含失败原因）
 * @param {string} reportId
 */
export const getReportProgress = (reportId) => {
  return service.get(`/api/report/${reportId}/progress`)
}

/**
 * الأقسام المكتوبة حتى الآن (لعرضها أثناء التوليد)
 * @param {string} reportId
 */
export const getReportSections = (reportId) => {
  return service.get(`/api/report/${reportId}/sections`)
}

/**
 * سيناريو مقارن: إعادة تشغيل جولات قصيرة على نفس المحاكاة بعد تغيير افتراض.
 * @param {string} reportId
 * @param {{change: string, rounds: number}} payload
 */
export const runReportScenario = (reportId, payload) => {
  return service.post(`/api/report/${reportId}/scenario`, payload, { timeout: 290000 })
}

/**
 * السيناريوهات المحفوظة لهذا التقرير
 * @param {string} reportId
 */
export const getReportScenarios = (reportId) => {
  return service.get(`/api/report/${reportId}/scenarios`)
}

/**
 * رابط تحميل مقارنة السيناريو بصيغة معيّنة
 * @param {string} reportId
 * @param {string} scenarioId
 * @param {string} format
 */
export const getScenarioDownloadUrl = (reportId, scenarioId, format = 'pdf') => {
  return `/api/report/${reportId}/scenario/${scenarioId}/download?format=${format}`
}
