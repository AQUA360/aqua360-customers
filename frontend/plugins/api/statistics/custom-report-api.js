// Informes personalitzats (consultes SQL desades): backend /statistics/custom-report/
export default defineNuxtPlugin(nuxtApp => {
    const entity = '/statistics/custom-report/';
    const provideName = 'CustomReportApiService';

    const { $apiManager } = useNuxtApp();
    const config = useRuntimeConfig();
    const apiHost = config.public.apiHost;
    const jsonHeaders = { 'Content-Type': 'application/json' };

    const getStatus = () => $apiManager.fetch(`${apiHost}${entity}status/`, 'GET');

    const getAll = (params = {}) => {
        const query = new URLSearchParams(params).toString();
        return $apiManager.fetch(`${apiHost}${entity}${query ? `?${query}` : ''}`, 'GET');
    };

    const get = (id) => $apiManager.fetch(`${apiHost}${entity}${id}/`, 'GET');

    const save = (data) => {
        const url = data.id ? `${apiHost}${entity}${data.id}/` : `${apiHost}${entity}`;
        const body = { title: data.title, description: data.description || '', sql: data.sql };
        return $apiManager.fetch(url, data.id ? 'PATCH' : 'POST', body, jsonHeaders);
    };

    const remove = (id) => $apiManager.fetch(`${apiHost}${entity}${id}/`, 'DELETE');

    const getSchema = () => $apiManager.fetch(`${apiHost}${entity}schema/`, 'GET');

    // Els errors de SQL es mostren dins la pàgina, no com a toast.
    const run = (id, params = {}) =>
        $apiManager.fetch(`${apiHost}${entity}${id}/run/`, 'POST', { params }, jsonHeaders, true);

    const runSql = (sql, params = {}) =>
        $apiManager.fetch(`${apiHost}${entity}run/`, 'POST', { sql, params }, jsonHeaders, true);

    const download = async (url, body) => {
        const authToken = localStorage.getItem('auth_token') || '';
        const response = await fetch(url, {
            method: 'POST',
            headers: { 'Authorization': `Token ${authToken}`, ...jsonHeaders },
            body: JSON.stringify(body),
        });
        if (!response.ok) {
            const errorData = await response.json().catch(() => ({}));
            throw new Error(errorData.error || errorData.detail || `HTTP ${response.status}`);
        }
        const disposition = response.headers.get('Content-Disposition') || '';
        const match = disposition.match(/filename="?([^";]+)"?/);
        const filename = match ? match[1].trim() : `report.${body.format}`;
        const blob = await response.blob();
        const blobUrl = URL.createObjectURL(blob);
        const link = document.createElement('a');
        link.href = blobUrl;
        link.download = filename;
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);
        setTimeout(() => URL.revokeObjectURL(blobUrl), 250);
        return { truncated: response.headers.get('X-Truncated') === 'true' };
    };

    const exportReport = (id, params = {}, format = 'xlsx') =>
        download(`${apiHost}${entity}${id}/export/`, { params, format });

    const exportSql = (sql, params = {}, format = 'xlsx', title = 'report') =>
        download(`${apiHost}${entity}export/`, { sql, params, format, title });

    nuxtApp.provide(provideName, {
        getStatus,
        getAll,
        get,
        save,
        remove,
        getSchema,
        run,
        runSql,
        exportReport,
        exportSql,
    });
});
