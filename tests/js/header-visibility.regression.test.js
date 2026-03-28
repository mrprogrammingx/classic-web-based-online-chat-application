/**
 * tests/js/header-visibility.regression.test.js
 * Ensure header-visibility checks /me with an Authorization header when a
 * JS-held token exists, and still includes credentials so cookie-based auth
 * continues to work.
 */

describe('header-visibility token usage', () => {
	beforeEach(() => {
		document.body.innerHTML = '<button id="admin-open" style="display:none"></button>';
		// clear any leftover appState or sessionStorage from other tests
		delete window.appState;
		try{ sessionStorage.clear(); }catch(e){}
	});

	afterEach(() => {
		jest.resetAllMocks && jest.resetAllMocks();
		delete window.appState;
		try{ sessionStorage.clear(); }catch(e){}
	});

	test('uses Authorization header when window.appState.token present', async () => {
		window.appState = { token: 'TESTTOKEN123' };
		const fetchMock = jest.fn((url, opts) => {
			expect(url).toBe('/me');
			// must include Authorization header
			expect(opts).toBeTruthy();
			expect(opts.credentials).toBe('include');
			expect(opts.headers['Authorization']).toBe('Bearer TESTTOKEN123');
			return Promise.resolve({ ok: true, json: () => Promise.resolve({ user: { id: 1, is_admin: 1 } }) });
		});
		global.fetch = fetchMock;
		// ensure we re-run the module initialization (clear require cache)
		try{ delete require.cache[require.resolve('../../static/header/header-visibility.js')]; }catch(e){}
		require('../../static/header/header-visibility.js');
		try{ window.dispatchEvent(new Event('shared-header-loaded')); }catch(e){}
		// wait up to 200ms for fetchMock to be called (poll)
		let waited = 0; while(!fetchMock.mock.calls.length && waited < 200){ await new Promise(r=>setTimeout(r, 5)); waited += 5; }
		expect(fetchMock).toHaveBeenCalled();
		const adminBtn = document.getElementById('admin-open');
		// wait for adminBtn.style.display to change to inline-flex (or timeout)
		waited = 0; while(adminBtn.style.display !== 'inline-flex' && waited < 200){ await new Promise(r=>setTimeout(r, 5)); waited += 5; }
		expect(adminBtn.style.display).toBe('inline-flex');
	});

	test('falls back to cookie-based fetch when no token', async () => {
		// no appState.token and no sessionStorage boot_token
		const fetchMock = jest.fn((url, opts) => {
			expect(url).toBe('/me');
			expect(opts).toBeTruthy();
			// no Authorization header in this case
			expect(opts.headers).toEqual({});
			expect(opts.credentials).toBe('include');
			return Promise.resolve({ ok: true, json: () => Promise.resolve({ user: { id: 2, is_admin: 0 } }) });
		});
		global.fetch = fetchMock;
		try{ delete require.cache[require.resolve('../../static/header/header-visibility.js')]; }catch(e){}
		require('../../static/header/header-visibility.js');
		try{ window.dispatchEvent(new Event('shared-header-loaded')); }catch(e){}
		let waited = 0; while(!fetchMock.mock.calls.length && waited < 200){ await new Promise(r=>setTimeout(r, 5)); waited += 5; }
		expect(fetchMock).toHaveBeenCalled();
		const adminBtn = document.getElementById('admin-open');
		// wait a tick for potential UI updates
		await new Promise(r=>setTimeout(r, 5));
		// user is not admin; button remains hidden
		expect(adminBtn.style.display).toBe('none');
	});
});

