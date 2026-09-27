/**
 * MAIN world interceptor — sayfanın kendi fetch / XMLHttpRequest'ini sarmalar.
 *
 * chrome.* API'lerine erişimi yoktur; yakalanan JSON yanıtları window.postMessage ile
 * aynı sekmedeki izole content.js'e iletilir. URL filtrelemesi content.js'te yapılır.
 * Sayfa davranışını asla bozmamalı: tüm yakalama kodu try/catch içinde, yanıt
 * gövdesi clone() üzerinden okunur ve orijinal Response/XHR aynen döner.
 */
(() => {
  const FLAG = '__dentaiPmsSyncPatched__';
  if (window[FLAG]) return;
  Object.defineProperty(window, FLAG, { value: true });

  const SOURCE = 'dentai-pms-sync';
  const MAX_BYTES = 5 * 1024 * 1024;

  function toAbsolute(url) {
    try {
      return new URL(url, window.location.href).href;
    } catch {
      return null;
    }
  }

  function emit(url, method, status, contentType, text) {
    if (typeof text !== 'string' || !text || text.length > MAX_BYTES) return;
    if (!contentType.includes('json') && !/^\s*[[{]/.test(text)) return;
    const absolute = toAbsolute(url);
    if (!absolute || new URL(absolute).origin !== window.location.origin) return;
    window.postMessage(
      { source: SOURCE, type: 'NETWORK_RESPONSE', url: absolute, method, status, body: text },
      window.location.origin,
    );
  }

  // ── fetch ────────────────────────────────────────────────────────────────
  const nativeFetch = window.fetch;
  window.fetch = async function patchedFetch(...args) {
    const response = await nativeFetch.apply(this, args);
    try {
      const [input, init] = args;
      const url = typeof input === 'string' ? input : input instanceof URL ? input.href : input?.url;
      const method = String(init?.method || (input instanceof Request ? input.method : 'GET')).toUpperCase();
      const contentType = response.headers.get('content-type') || '';
      const length = Number(response.headers.get('content-length') || 0);
      if (url && (contentType.includes('json') || contentType.includes('text')) && length <= MAX_BYTES) {
        response
          .clone()
          .text()
          .then((text) => emit(url, method, response.status, contentType, text))
          .catch(() => {});
      }
    } catch {
      /* sayfa akışını etkileme */
    }
    return response;
  };

  // ── XMLHttpRequest ───────────────────────────────────────────────────────
  const proto = XMLHttpRequest.prototype;
  const nativeOpen = proto.open;
  const nativeSend = proto.send;
  const meta = new WeakMap();

  proto.open = function patchedOpen(method, url, ...rest) {
    meta.set(this, { method: String(method || 'GET').toUpperCase(), url: String(url) });
    return nativeOpen.call(this, method, url, ...rest);
  };

  proto.send = function patchedSend(...args) {
    const info = meta.get(this);
    if (info) {
      this.addEventListener(
        'load',
        () => {
          try {
            const contentType = this.getResponseHeader('content-type') || '';
            let text = null;
            if (this.responseType === '' || this.responseType === 'text') text = this.responseText;
            else if (this.responseType === 'json' && this.response !== null) text = JSON.stringify(this.response);
            if (text) emit(info.url, info.method, this.status, contentType, text);
          } catch {
            /* sayfa akışını etkileme */
          }
        },
        { once: true },
      );
    }
    return nativeSend.apply(this, args);
  };
})();
