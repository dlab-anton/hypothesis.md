const NO_STORE = "private, no-store, max-age=0";

export function apiUpstream(): string {
  return process.env.HYPOTHESIS_API_URL || "http://localhost:8000/api/v1";
}

/** Fixed operator-configured destination. Never forward browser cookies or redirects off-origin. */
export async function proxyApiRequest(
  request: Request,
  path: string[],
  upstream = apiUpstream(),
  fetcher: typeof fetch = fetch,
): Promise<Response> {
  const headers = new Headers({
    "Cache-Control": NO_STORE,
    "CDN-Cache-Control": "no-store",
    "Vercel-CDN-Cache-Control": "no-store",
  });
  try {
    const base = new URL(upstream);
    if (!['http:', 'https:'].includes(base.protocol) || base.username || base.password ||
        base.search || base.hash || base.pathname.replace(/\/$/, '') !== '/api/v1' ||
        (process.env.NODE_ENV === 'production' && base.protocol !== 'https:')) {
      throw new Error('Invalid API upstream');
    }
    if (path.some(part => part === '.' || part === '..' || /[\\/]/.test(part))) {
      return Response.json({ detail: 'Invalid API path' }, { status: 400, headers });
    }
    const destination = new URL(`/api/v1/${path.map(encodeURIComponent).join('/')}`, base.origin);
    destination.search = new URL(request.url).search;
    const forwarded = new Headers();
    for (const name of ['x-api-key', 'content-type', 'accept', 'idempotency-key']) {
      const value = request.headers.get(name);
      if (value) forwarded.set(name, value);
    }
    const init: RequestInit & { duplex?: 'half' } = {
      method: request.method, headers: forwarded, cache: 'no-store',
      credentials: 'omit', redirect: 'manual',
      signal: AbortSignal.any([request.signal, AbortSignal.timeout(30_000)]),
    };
    if (request.method !== 'GET' && request.method !== 'HEAD') {
      init.body = request.body;
      init.duplex = 'half';
    }
    const response = await fetcher(destination, init);
    for (const name of ['content-type', 'content-disposition', 'retry-after', 'www-authenticate']) {
      const value = response.headers.get(name);
      if (value) headers.set(name, value);
    }
    const location = response.headers.get('location');
    if (location) {
      const redirect = new URL(location, destination);
      if (redirect.origin !== base.origin || !redirect.pathname.startsWith('/api/v1/')) {
        await response.body?.cancel();
        return Response.json({ detail: 'Invalid API redirect' }, { status: 502, headers });
      }
      headers.set('location', `${redirect.pathname}${redirect.search}${redirect.hash}`);
    }
    return new Response(response.body, { status: response.status, statusText: response.statusText, headers });
  } catch {
    // Deliberately omit URLs, headers, and exception text: all can carry credentials.
    return Response.json({ detail: 'The research API is temporarily unavailable.' }, { status: 502, headers });
  }
}
