/**
 * ISOLATED world köprüsü — injected.js (MAIN) ↔ background service worker.
 *
 * Background'dan sağlayıcının intercept URL desenlerini alır; eşleşen başarılı JSON
 * yanıtlarını PMS_INTERCEPT mesajıyla iletir. DentAI oturumu yoksa desen listesi boş
 * gelir ve hiçbir veri sekmeden dışarı çıkmaz.
 */
(() => {
  const SOURCE = 'dentai-pms-sync';
  const MAX_PENDING = 20;

  let patterns = null;
  const pending = [];

  function contextAlive() {
    try {
      return Boolean(chrome.runtime?.id);
    } catch {
      return false;
    }
  }

  function forward(data) {
    if (!patterns.length || data.status < 200 || data.status >= 300) return;
    if (!patterns.some((re) => re.test(data.url))) return;
    if (!contextAlive()) return;
    chrome.runtime
      .sendMessage({ type: 'PMS_INTERCEPT', url: data.url, method: data.method, body: data.body })
      .catch(() => {});
  }

  async function loadConfig() {
    try {
      const config = await chrome.runtime.sendMessage({ type: 'GET_INTERCEPT_CONFIG' });
      patterns = (config?.patterns || []).map((src) => new RegExp(src, 'i'));
    } catch {
      patterns = [];
    }
    pending.splice(0).forEach(forward);
  }

  window.addEventListener('message', (event) => {
    if (event.source !== window || event.origin !== window.location.origin) return;
    const data = event.data;
    if (!data || data.source !== SOURCE || data.type !== 'NETWORK_RESPONSE') return;
    if (typeof data.url !== 'string' || typeof data.body !== 'string') return;

    if (patterns === null) {
      if (pending.length < MAX_PENDING) pending.push(data);
      return;
    }
    forward(data);
  });

  chrome.storage.onChanged.addListener((changes, area) => {
    if (area === 'local' && 'dentai:auth' in changes && contextAlive()) loadConfig();
  });

  loadConfig();
})();
